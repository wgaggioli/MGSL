import logging
import os
import subprocess
import paramiko
from pynecroud.util import temporary_file

log = logging.getLogger(__name__)


class ServerRunner(object):
    """Run commands and such on a live server"""

    def __init__(self, host, user, key_path=None):
        self.host = host
        self.user = user
        self.key_path = key_path
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = paramiko.SSHClient()
            if self.key_path:
                self._key = paramiko.RSAKey.from_private_key_file(
                    self.key_path)
            else:
                self._key = None
            self._conn.load_system_host_keys()
            self._conn.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
            self._conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._conn.connect(self.host, username=self.user, pkey=self._key)

        return self._conn

    def upload(self, local_file, remote_file, as_root=False, verbose=True):
        if verbose:
            log.info('Uploading {} to {}'.format(local_file, remote_file))

        if as_root:
            full_remote = '{user}@{host}:{remote_file}'.format(
                user=self.user,
                host=self.host,
                remote_file=os.path.basename(remote_file)
            )
        else:
            full_remote = '{user}@{host}:{remote_file}'.format(
                user=self.user,
                host=self.host,
                remote_file=remote_file
            )

        subprocess.check_call(
            ['scp', '-i', self.key_path, local_file, full_remote])

        if as_root:
            self.run_cmd('sudo cp {fname} {remote_file}'.format(
                fname=os.path.basename(remote_file),
                remote_file=remote_file))

    def download(self, remote_file, local_folder, verbose=True):
        if verbose:
            log.info('Downloading {} to {}'.format(remote_file, local_folder))

        if not local_folder.endswith('/'):
            local_folder += '/'

        full_remote = '{user}@{host}:{remote_file}'.format(
            user=self.user,
            host=self.host,
            remote_file=remote_file
        )
        subprocess.check_call(
            ['scp', '-i', self.key_path, full_remote, local_folder])

    def run_cmd(self, cmd, verbose=True, quiet=False, sub_params=None, **kw):
        if verbose:
            log.info('Running {} on {}'.format(cmd, self.host))
        if sub_params:
            cmd = cmd.format(**sub_params)
        stdin, stdout, stderr = self.conn.exec_command(cmd, **kw)
        if not quiet:
            log.info(stdout.read())
            err = stderr.read()
            if err:
                log.warn(err)

    def run_script(self, script_path, sub_params=None, shell='bash', **kw):
        log.info(
            'Running local script {} on {}'.format(script_path, self.host))
        remote_file = os.path.basename(script_path)
        if sub_params:
            with temporary_file(text=True) as (fpw, fname):
                with open(script_path, 'r') as fpr:
                    raw_script = fpr.read()
                    fpw.write(raw_script.format(**sub_params))
                fpw.flush()
                script_path = fname
                self.upload(script_path, remote_file)
        else:
            self.upload(script_path, remote_file)

        cmd = '{shell} {remote_file}'.format(
            shell=shell, remote_file=remote_file)
        self.run_cmd(cmd, **kw)
        self.run_cmd('rm ' + remote_file)
