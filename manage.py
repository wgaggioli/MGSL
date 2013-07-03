import os
import argparse

from pynecroud.cmd import (
    SaveCommand,
    LoadCommand,
    KillCommand,
    StartCommand,
    ChangeWorldCommand,
    ChangeInstanceTypeCommand
)

commands = {
    'save': SaveCommand,
    'kill': KillCommand,
    'load': LoadCommand,
    'start': StartCommand,
    'change_world': ChangeWorldCommand,
    'change_instance_type': ChangeInstanceTypeCommand
}

HELP_TEXT = """
Pynecroud command line utility will place the power of Pynecroud at your
fingertips. To use, specify a command from below. To get help on a command,
use python manage.py COMMAND -- -h
\n\n
AVAILABLE COMMANDS
----
{command_list}

""".format(command_list='\n'.join(commands.keys()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=HELP_TEXT)
    parser.add_argument('command', choices=commands.keys())

    args, remainder = parser.parse_known_args()
    cmd_kls = commands[args.command]
    cmd = cmd_kls.from_args_list(remainder)
    cmd.full_run()
