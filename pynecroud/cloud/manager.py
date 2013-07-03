import logging
import os
import time

from boto import ec2
from boto.manage.cmdshell import sshclient_from_instance
from boto.exception import EC2ResponseError, BotoClientError
from pynecroud.exceptions import PynecroudError

log = logging.getLogger(__name__)


class ServerManager(object):

    def __init__(self, config):
        self.config = config

    def launch_instance(self, *args, **kwargs):
        raise NotImplementedError('launch_instance')

    def kill_instance(self, *args, **kwargs):
        raise NotImplementedError('kill_instance')

    def _wait(self, *args, **kw):
        raise NotImplementedError('wait')


class EC2Manager(ServerManager):

    SECURITY_PORT_SPEC = [
        ['icmp', '-1', '-1'],
        ['tcp', '22', '22'],
        ['tcp', '25565', '25565'],
        ['udp', '25565', '25565']
    ]

    def __init__(self, config):
        super(EC2Manager, self).__init__(config)
        kw_params = {
            "aws_access_key_id": config['aws_access_key_id'],
            "aws_secret_access_key": config['aws_secret_access_key']
        }
        if config.get('aws_region'):
            self.ec2_connection = ec2.connect_to_region(
                config['aws_region'], **kw_params)
        else:
            self.ec2_connection = ec2.EC2Connection(**kw_params)
        self.instance = None
        self.key_path = None

    def _get_or_create_security_group(self, group_name):
        try:
            group = self.ec2_connection.get_all_security_groups(
                groupnames=[group_name])[0]
            log.info('Found group %s', group_name)
        except self.ec2_connection.ResponseError, err:
            if err.code == 'InvalidGroup.NotFound':
                group = self.ec2_connection.create_security_group(
                    group_name, group_name)
                log.info('Group %s not found, creating...', group_name)

                for port in self.SECURITY_PORT_SPEC:
                    self.ec2_connection.authorize_security_group(
                        group_name,
                        ip_protocol=port[0],
                        from_port=port[1],
                        to_port=port[2],
                        cidr_ip='0.0.0.0/0')
            else:
                raise
        return group

    def _get_or_create_keyname(self, key_name, key_dir='~/.ssh',
                               clear_knownhosts=False):
        key = self.ec2_connection.get_key_pair(key_name)
        if key is None:
            log.info('Creating new key_pair {} for instance'.format(key_name))

            # Create an SSH key to use when logging into instances.
            key = self.ec2_connection.create_key_pair(key_name)

            # Make sure the specified key_dir actually exists.
            # If not, create it.
            key_dir = os.path.expanduser(key_dir)
            key_dir = os.path.expandvars(key_dir)
            if not os.path.isdir(key_dir):
                os.mkdir(key_dir, 0700)

            # AWS will store the public key but the private key is
            # generated and returned and needs to be stored locally.
            # The save method will also chmod the file to protect
            # your private key.
            try:
                key.save(key_dir)
            except BotoClientError:
                self.ec2_connection.delete_key_pair(key_name)
                raise

            if clear_knownhosts:
                with open(os.path.join(key_dir, 'known_hosts'), 'w') as fp:
                    fp.write('')

        return key

    def launch_instance(self, ami, group_name='minecraft',
                        key_name='minecraft', instance_type='t1.micro',
                        instance_name='minecraft', key_dir='~/.ssh',
                        key_ext='.pem', login_user='ubuntu', block=True, **kw):
        security_group = self._get_or_create_security_group(group_name)
        key = self._get_or_create_keyname(
            key_name, key_dir, clear_knownhosts=True)
        self.key_path = os.path.join(
            os.path.expanduser(key_dir),
            key_name + key_ext)

        log.info('Spinning up [{}] of type {}'.format(ami, instance_type))
        reservation = self.ec2_connection.run_instances(
            ami, instance_type=instance_type, key_name=key_name,
            security_groups=[security_group], **kw)

        # wait for reservation to complete
        if instance_name or block:
            for r in self.ec2_connection.get_all_instances():
                if r.id == reservation.id:
                    break

            self.instance = reservation.instances[-1]
            self.ec2_connection.create_tags(
                [self.instance.id], {"Name": instance_name})

            if block:
                self._wait(self.key_path, login_user=login_user)

    def _wait(self, key_path, login_user='ubuntu', sleep_time=2):
        """Wait for ssh access to instance"""
        if not self.instance:
            raise PynecroudError('Must launch instance first')

        log.info('Waiting for instance availability...')
        while not self.instance.update() == 'running':
            time.sleep(sleep_time)

        log.info('Waiting for ssh access...')
        sshclient_from_instance(self.instance, key_path, user_name=login_user)

    def kill_instance(self, instance_id=None, dns_name=None):
        if not instance_id and not dns_name:
            raise PynecroudError('Must specify instance_id or dns_name')
        log.info('Killing instance {}'.format(instance_id or dns_name))
        if instance_id:
            self.ec2_connection.terminate_instances(
                instance_ids=[instance_id])
        else:
            resp = self.ec2_connection.get_all_instances(
                filters={'dns-name': dns_name})
            resp[0].instances[0].terminate()
