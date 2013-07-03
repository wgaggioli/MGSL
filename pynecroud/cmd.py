import logging
import json
import argparse
import os
import time

import pynecroud
from pynecroud.cloud.manager import EC2Manager
from pynecroud.cloud.runner import ServerRunner
from pynecroud.craft import MineCraftServer
from pynecroud.exceptions import InvalidConfig
from pynecroud.util import parse_config

log = logging.getLogger(__name__)


class BaseCommand(object):
    parser = argparse.ArgumentParser(description='base cmd', add_help=False)
    parser.add_argument('--world', default='myworld')
    parser.add_argument('--config', default='config.ini')
    parser.add_argument('--local_cache', default='data/.pynecroud')
    parser.add_argument('--log_level', default='INFO')
    needs_config = True

    def __init__(self, options, config):
        self.options = options
        self.config = config
        self._local_cache = None
        logging.basicConfig(level=getattr(logging, options.log_level))

    @property
    def local_cache(self):
        if self._local_cache is None:
            if self.options.local_cache and os.path.exists(
                    self.options.local_cache):
                with open(self.options.local_cache, 'r') as fp:
                    self._local_cache = json.load(fp)
            else:
                self._local_cache = {}
        return self._local_cache

    def write_local_cache(self):
        with open(self.options.local_cache, 'w') as fp:
            json.dump(self.local_cache, fp)

    def _get_option(self, key, default=None):
        value = getattr(self.options, key, None) or self.config.get(key)
        if value is None:
            value = self.local_cache.get(key, default)
        return value

    def help_text(self):
        return self.parser.description

    def run(self):
        raise NotImplementedError

    @classmethod
    def from_args_list(cls, args):
        options = cls.parser.parse_args(args)
        if cls.needs_config:
            config = parse_config(options.config, options.world)
        else:
            config = None
        return cls(options, config)


class KillCommand(BaseCommand):
    """Terminate an instance"""
    parser = argparse.ArgumentParser(
        prog='python manage.py kill --',
        description='Kill a server',
        parents=[BaseCommand.parser])

    manager_cls = EC2Manager

    parser.add_argument('--instance_id', help="ID of the instance to kill")
    parser.add_argument('--host', help="DNS Name of the instance to kill")

    def run(self):
        instance_id = self._get_option('instance_id')
        host = self._get_option('host')
        if instance_id is None and host is None:
            raise InvalidConfig(
                'Must supply either the instance_id or the host')

        manager = self.manager_cls(self.config)
        manager.kill_instance(instance_id, host)


class StartCommand(BaseCommand):
    parser = argparse.ArgumentParser(
        prog='python manage.py start --',
        description='Start a server and install minecraft, optionally loading '
                    'a world unto it',
        parents=[BaseCommand.parser])

    # These are optional and can be supplied by the config and the local cache
    parser.add_argument('--ami', help="Amazon Machine Image ID")
    parser.add_argument(
        '--security_group', help="Security group, if missing will create")
    parser.add_argument(
        '--instance_type', help="Instance type")
    parser.add_argument('--key_name', help="Key name of the instance")
    parser.add_argument('--instance_name', help="Name of the instance")
    parser.add_argument('--login_user', help='OS user on remote server')

    manager_cls = EC2Manager

    def _get_launcher_args(self):
        """This is EC2 specific"""
        ami = self._get_option('ami')
        if ami is None:
            raise InvalidConfig('Must supply AMI')
        args = (ami,)
        kwargs = {
            "group_name": self._get_option('security_group', 'minecraft'),
            "instance_type": self._get_option('instance_type', 't1.micro'),
            "instance_name": self._get_option('instance_name', 'minecraft'),
            "key_name": self._get_option('key_name', 'minecraft'),
            "login_user": self._get_option('login_user', 'ubuntu')
        }

        # update cache
        self.local_cache.update(kwargs)
        self.local_cache['ami'] = ami

        return args, kwargs

    def launch_instance(self, block=True):
        launcher = self.manager_cls(self.config)
        args, kwargs = self._get_launcher_args()
        kwargs['block'] = block
        log.debug('Launching instance with args {} and kwargs {}'.format(
            args, kwargs))
        launcher.launch_instance(*args, **kwargs)
        return launcher

    def run(self):
        start_t = time.time()
        launcher = self.launch_instance()
        user = self._get_option('login_user', 'ubuntu')
        runner = ServerRunner(
            launcher.instance.dns_name,
            user,
            key_path=launcher.key_path)
        self.mcs = MineCraftServer(runner)
        self.mcs.install()

        # writing is ec2 specific
        self.local_cache.update({
            "instance_id": launcher.instance.id,
            "host": runner.host,
            "key": launcher.key_path,
        })
        self.write_local_cache()
        log.critical('Instance is at {}'.format(runner.host))
        log.info('Finished in {:0.2f} seconds'.format(time.time() - start_t))


class _BaseRunning(BaseCommand):
    """Base Command for running ops on a running instance"""
    parser = argparse.ArgumentParser(
        add_help=False, parents=[BaseCommand.parser])

    parser.add_argument('--login_user', help='OS user on remote server')
    parser.add_argument('--host', help='IP of remote server')
    parser.add_argument('--key', help='Path to private key')

    def get_server(self):
        host = self._get_option('host')
        user = self._get_option('login_user')
        key_path = self._get_option(
            'key', os.path.expanduser('~/.ssh/minecraft.pem'))
        if not host or not user:
            raise InvalidConfig('Host and user required')
        runner = ServerRunner(host, user, key_path)
        mcs = MineCraftServer(runner)
        return mcs


class SaveCommand(_BaseRunning):
    parser = argparse.ArgumentParser(
        prog='python manage.py save --',
        description='Save a world to the local filesystem',
        parents=[_BaseRunning.parser])

    parser.add_argument('--data_folder', help='Folder to save world data')

    def run(self):
        mcs = self.get_server()
        world = self._get_option('world', 'world')
        default_data_dir = os.path.join(
            pynecroud.__path__[0], os.pardir, 'data')
        local_folder = self._get_option('data_folder', default_data_dir)
        mcs.save_world_to_local(world, local_folder)
        self.local_cache.update({
            "data_folder": local_folder,
            "host": mcs.runner.host,
            "login_user": mcs.runner.user,
            "key": mcs.runner.key_path,
            "world": world
        })
        self.write_local_cache()


class LoadCommand(_BaseRunning):
    """Load saved data onto server"""
    parser = argparse.ArgumentParser(
        prog='python manage.py load --',
        description='Load a world from the local filesystem to the server',
        parents=[_BaseRunning.parser])

    parser.add_argument('--data_folder',
                        help='Folder where world data is saved')

    def run(self):
        mcs = self.get_server()
        world = self._get_option('world', 'world')
        local_folder = self._get_option('data_folder')
        mcs.load_world_on_server(world, local_folder)
        self.local_cache.update({
            "data_folder": local_folder,
            "host": mcs.runner.host,
            "login_user": mcs.runner.user,
            "key": mcs.runner.key_path,
            "world": world
        })
        self.write_local_cache()


class ChangeWorldCommand(_BaseRunning):
    """Change world for a given server"""
    def run(self):
        mcs = self.get_server()
        world = getattr(self.options, 'world') or self.config.get('world')
        if not world:
            raise InvalidConfig('Must specify the world to change to')
        mcs.change_world(world)


class ChangeInstanceTypeCommand(StartCommand):
    """
    Upgrade Downgrade instance type.

    A shortcut for save start load [kill]

    """
    parser = argparse.ArgumentParser(
        prog='python manage.py change_instance_type --',
        description='Upgrade or downgrade a server. A shortcut for save '
                    'start load [kill]',
        parents=[BaseCommand.parser])

    manager_cls = EC2Manager

    # cmd params
    parser.add_argument(
        '--no_kill', action='store_false', dest='kill', default=True,
        help='Do not kill the old instance')
    parser.add_argument('--data_folder', help='Folder to save world data')

    # params for new instance
    parser.add_argument('--ami', help="Amazon Machine Image ID")
    parser.add_argument(
        '--security_group', help="Security group for new instance")
    parser.add_argument(
        '--instance_type', help="Instance type of the new instance")
    parser.add_argument('--key_name', help="Key name of the new instance")
    parser.add_argument('--instance_name', help="Name of the new instance")
    parser.add_argument('--login_user', help='OS user on new server')

    # params for current instance
    parser.add_argument('--cur_host', help="IP of the current host")
    parser.add_argument('--cur_user', help="OS user on current server")
    parser.add_argument('--cur_key', help='Path to private key for current')

    def run(self):
        start_t = time.time()

        # current instance params (default to reading local cache)
        cur_host = self.options.cur_host or self.local_cache.get('cur_host')
        if not cur_host:
            raise InvalidConfig('Must specify cur_host')
        cur_user = self.options.cur_user or self.local_cache.get('cur_user')
        if not cur_user:
            raise InvalidConfig('Must specify cur_user')
        key_path = self.options.cur_key or self.local_cache.get(
            'key', os.path.expanduser('~/.ssh/minecraft.pem'))

        # start new instance
        StartCommand.run(self)

        # save current state
        log.info('Saving current world...')
        runner0 = ServerRunner(cur_host, cur_user, key_path)
        mcs0 = MineCraftServer(runner0)
        world = self._get_option('world', 'world')
        default_data_dir = os.path.join(
            pynecroud.__path__[0], os.pardir, 'data')
        local_folder = self._get_option('data_folder', default_data_dir)
        mcs0.save_world_to_local(world, local_folder)
        if self.options.kill:
            mcs0.stop()  # might as well end it now

        # load onto new server
        log.info('Loading data onto new server...')
        self.mcs.load_world_on_server(world, local_folder)
        self.local_cache.update({
            "data_folder": local_folder,
            "world": world
        })

        # optionally kill old
        if self.options.kill:
            log.info('Killing {}'.format(cur_host))
            manager = self.manager_cls(self.config)
            manager.kill_instance(dns_name=cur_host)

        log.info('Finished in {:0.2f} seconds'.format(time.time() - start_t))
