#!/usr/bin/env python3

import sys

from gevent import os

SERVER = None  # noqa

if not os.environ.get('SLR_LOCAL_ENV'):  # noqa
    import gevent.monkey

    gevent.monkey.patch_all()

    import psycogreen.gevent
    psycogreen.gevent.patch_psycopg()

    SERVER = 'gevent'

import logging
import warnings

from flask.exthook import ExtDeprecationWarning

from app.config import DEBUG

warnings.filterwarnings('ignore', category=ExtDeprecationWarning)  # noqa

__version__ = '0.1'

level = logging.INFO if not DEBUG else logging.DEBUG
logging.basicConfig(level=level)
logging.handlers = [logging.StreamHandler(stream=sys.stdout)]
