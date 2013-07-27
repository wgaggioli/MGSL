# Pynecroud
Python - Minecraft - Cloud

A Minecraft Game Server Launcher and Manager

## Use Case
The primary use case envisioned for this tool is to run a minecraft server for
small groups of people on-demand, and not have to pay for 100% server uptime.

Pynecroud uses EC2 (though in the future I will support other cloud platforms),
so you will want an account there.

## Install
In the terminal, type:

    python setup.py install

Then add your EC2 credentials and info to `config.ini`.

## How to Use
When I come home from work and my buddies want to play, I would type in the
terminal:

    python manage.py start

That starts a new server and outputs the resulting host. (If you forget, it's
stored in data/.pynecroud as a JSON object).

Then when we're done playing, I simply do:

    python manage.py save
    python manage.py kill

That saves the world state and then terminates the ec2 instance, because nobody
wants to be paying for that.

The next time you want to play, simply do:

    python manage.py start
    python manage.py load

To load your old world onto the new instance.

Another common situation we ran into is that most of the time an ec2 micro
instance was fine, but when we had more than 3 people or even 3 or less people
but we were more spread out (bigger demand on the server), the micro suddenly
could not handle the load. In such situations, you can simply do:

    python manage.py change_instance_type --instance_type m1.small

Which will kill your old instance and load it on to a new small instance. When
you're done, simply do the opposite:

    python manage.py change_instance_type --instance_type t1.micro

Type `python manage.py -h` for a full list of commands and options.

## Configure
Most options to the command can be added to the config.ini in the root of the
project. This can help with distributed players where multiple people are using
the tool. You can configure on a world-by-world basis by using world names
as section headers in the config:

    [myworld]
    instance_type = m1.large

One big gotcha if you want to specify the AMI of the instance is that you have
to specify the region as well. This defaults to Ubuntu 12.04 LTS in us-west-1.

## Future

  - Add pluggable storage for game worlds, and add S3 and SFTP storage providers (right now its local, which can cause problems)
  - Web interface
  - Support for different clouds other than EC2

Thanks to [dirkk0](https://github.com/dirkk0) and others for inspiration and
contributions.
