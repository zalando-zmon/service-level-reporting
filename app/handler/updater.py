import logging
import os
import time

from connexion import ProblemException

from app.db import dbconn, database_uri
from app.handler.product import get as get_products
from app.slo import process_sli

MAX_QUERY_TIME_SLICE = os.getenv('MAX_QUERY_TIME_SLICE', 1440)


logger = logging.getLogger('sli-update')


def run_sli_update():
    while True:
        time.sleep(int(os.getenv('UPDATE_INTERVAL_SECONDS', 600)))
        try:
            for product in get_products():
                try:
                    update_service_level_objectives(product['slug'])
                except:
                    logger.exception('Failed to update SLIs for product: {}'.format(product.get('slug')))
        except:
            logger.exception('Failed to update SLIs')


def update_service_level_objectives(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT f.sli_name AS sli_name, seconds_ago  FROM zsm_data.service_level_indicators_full AS f
                      LEFT OUTER JOIN zsm_data.sli_latest_data AS l ON f.sli_name=l.sli_name AND f.p_id=l.p_id
                      WHERE f.p_slug = %s''', (product,))
        rows = cur.fetchall()
    res = {}
    for row in rows:
        start_time = ((row.seconds_ago // 60) + 5) if row.seconds_ago else MAX_QUERY_TIME_SLICE
        res[row.sli_name] = {'start': start_time}
        response = post_update(product, row.sli_name, res[row.sli_name])
        res[row.sli_name]['count'] = response['count']
    return res


def post_update(product, name, body):
    kairosdb_url = os.getenv('KAIROSDB_URL')
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT ds_definition FROM zsm_data.data_source WHERE '
            'ds_product_id = (SELECT p_id FROM zsm_data.product WHERE p_slug = %s) AND ds_sli_name = %s',
            (product, name))
        row = cur.fetchone()
        if not row:
            return 'Not found', 404
        definition, = row

    start = body.get('start', MAX_QUERY_TIME_SLICE)
    end = body.get('end')

    if end and end >= start:
        raise ProblemException(
            title='Invalid "end" field value', detail='"end" field should be less than "start" field value')

    count = process_sli(product, name, definition, kairosdb_url, start, end, 'minutes', database_uri)

    return {'count': count}


def local():
    for product in get_products():
        update_service_level_objectives(product['slug'])


if __name__ == '__main__':
    local()
