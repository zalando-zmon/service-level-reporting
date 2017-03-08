#!/usr/bin/env python3
import gevent.monkey

gevent.monkey.patch_all()  # noqa

import psycogreen.gevent
psycogreen.gevent.patch_psycopg()  # noqa

import logging
import os

from decimal import Decimal

import connexion
from connexion.decorators.produces import JSONEncoder
from app.handler.updater import run_sli_update


class DecimalEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)

        return super().default(o)


logging.basicConfig(level=logging.INFO)
app = connexion.App(__name__)
app.app.json_encoder = DecimalEncoder
swagger_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'swagger.yaml')
app.add_api(swagger_path)
# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8080 -w app
application = app.app


def run():
    gevent.spawn(run_sli_update)
    # run our standalone gevent server
    app.run(port=8080, server='gevent')


if __name__ == '__main__':
    run()
