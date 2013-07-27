from contextlib import contextmanager
import os

import pynecroud
from pynecroud.exceptions import PynecroudError
from pynecroud.util import temporary_file


class MineCraftServer(object):

    SCRIPT_DIR = os.path.join(pynecroud.__path__[0], 'scripts')

    def __init__(self, runner):
        self.runner = runner

    def _script_path(self, script_name):
        return os.path.join(self.SCRIPT_DIR, script_name)

    def install(self, world='world', memory='1024M', allocate_swap=False):
        self.runner.run_script(self._script_path('init.sh'))
        self.runner.run_script(
            self._script_path('new.sh'),
            sub_params={'world_name': world})
        if allocate_swap:
            self.runner.run_script(self._script_path('allocate_swap.sh'))
        script_path = self._script_path('conf/minecraft-server.conf')
        self.runner.upload(
            script_path, '/etc/init/minecraft-server.conf', as_root=True,
            subparams={'memory': 'memory'})
        self.start()
        if world != 'world':
            with self.lower_server():
                self.change_world(world)

    def stop(self):
        self.runner.run_script(self._script_path('stop.sh'))

    def start(self):
        self.runner.run_script(self._script_path('start.sh'))

    def change_world(self, world):
        with self.lower_server():
            self.runner.run_script(
                self._script_path('change_world.sh'),
                sub_params={"world_name": world})

    @contextmanager
    def lower_server(self):
        self.stop()
        try:
            yield
        finally:
            self.start()

    def save_world_to_local(self, world, local_folder):
        with self.lower_server():
            self.runner.run_script(
                self._script_path('save.sh'), sub_params={'world_name': world})
        saved = '~/{world}.tar.gz'.format(world=world)
        local_path = os.path.join(local_folder, os.path.basename(saved))
        if os.path.exists(local_path):
            os.remove(local_path)
        self.runner.download(saved, local_folder)
        self.runner.run_cmd('rm ' + saved)

    def load_world_on_server(self, world, local_folder):
        self.stop()
        fname = world + '.tar.gz'
        local_path = os.path.join(local_folder, fname)
        if not os.path.exists(local_path):
            raise PynecroudError('{} does not exist'.format(local_path))
        self.runner.upload(local_path, fname)

        with self.lower_server():
            self.runner.run_script(
                self._script_path('load.sh'), sub_params={'world_name': world})
