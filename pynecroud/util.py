import os
import ConfigParser
import tempfile
from contextlib import contextmanager


def parse_config(path, world):
    config = ConfigParser.SafeConfigParser({
        'world': world,
        'here': os.path.dirname(os.path.abspath(path))
    })
    with open(path, 'r') as fp:
        config.readfp(fp)
    try:
        conf = config.items(world)
    except ConfigParser.NoSectionError:
        conf = config.items('DEFAULT')
    return dict(conf)


@contextmanager
def temporary_file(text=False, **kw):
    """Create a temporary file, then delete it when finished"""
    fd, fname = tempfile.mkstemp(text=text, **kw)
    mode = 'w+' if text else 'wb+'
    fp = os.fdopen(fd, mode)
    try:
        yield (fp, fname)
    finally:
        fp.close()
        os.remove(fname)
