#!/usr/bin/env python3

import gevent.monkey
gevent.monkey.patch_all()

import psycogreen.gevent
psycogreen.gevent.patch_psycopg()

import connexion
import logging
import os
import psycopg2
import psycopg2.pool
from psycopg2.extras import NamedTupleCursor

import slo

database_uri = os.getenv('DATABASE_URI')
# NOTE: we can safely use SimpleConnectionPool instead of ThreadedConnectionPool as we use gevent greenlets
pool = psycopg2.pool.SimpleConnectionPool(1, 10, database_uri, cursor_factory=NamedTupleCursor)

def get_health():
    return 'OK'

def get_service_level_indicators(product, name):
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT sli_timestamp, sli_value from zsm_data.service_level_indicator WHERE sli_product_id = (SELECT p_id FROM zsm_data.product WHERE p_name = %s) AND sli_name = %s', (product, name))
        return cur.fetchall()
    finally:
        pool.putconn(conn)


def post_update(body):
    kairosdb_url = os.getenv('KAIROSDB_URL')
    slo.update(body.get('definitions'), kairosdb_url, database_uri, body.get('start', 5), 'minutes')
    return ''

logging.basicConfig(level=logging.INFO)
app = connexion.App(__name__)
app.add_api('swagger.yaml')
# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8080 -w app
application = app.app

if __name__ == '__main__':
    # run our standalone gevent server
    app.run(port=8080, server='gevent')
