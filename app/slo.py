#!/usr/bin/env python3

import datetime
import fnmatch
import logging
import os

import psycopg2
import requests
import zign.api

logger = logging.getLogger('slo')
KAIROS_QUERY_LIMIT = os.getenv('KAIROS_QUERY_LIMIT', 10000)


def key_matches(key, key_patterns):
    for pat in key_patterns:
        if fnmatch.fnmatch(key, pat):
            return True
    return False


def process_sli(product_name, sli_name, sli_def, kairosdb_url, start, end, time_unit, dsn):
    logger.info('Calculating SLI for %s/%s..', product_name, sli_name)
    check_id = sli_def['check_id']
    keys = sli_def['keys']
    exclude_keys = sli_def.get('exclude_keys', [])
    aggregation_type = sli_def['aggregation']['type']

    kairosdb_metric_name = 'zmon.check.{}'.format(check_id)

    token = zign.api.get_token('zmon', ['uid'])
    headers = {'Authorization': 'Bearer {}'.format(token)}

    session = requests.Session()
    session.headers.update(headers)

    tags = {'key': keys + sli_def['aggregation'].get('weight_keys', [])}
    if sli_def.get('tags'):
        tags.update(sli_def['tags'])
    q = {
        'start_relative': {
            'value': start,
            'unit': time_unit
        },
        'metrics': [{
            'name': kairosdb_metric_name,
            'tags': tags,
            'limit': KAIROS_QUERY_LIMIT,
            'group_by': [{'name': 'tag', 'tags': ['entity', 'key']}]
        }]
    }

    if end:
        q['end_relative'] = {'value': end, 'unit': time_unit}

    response = session.post(kairosdb_url + '/api/v1/datapoints/query', json=q)
    response.raise_for_status()

    data = response.json()

    res = {}
    for result in data['queries'][0]['results']:
        group = result['group_by'][0]['group']
        key = group['key']
        exclude = key_matches(key, exclude_keys)
        if not exclude:
            for ts, value in result['values']:
                # truncate to full minutes
                minute = (ts // 60000) * 60
                if minute not in res:
                    res[minute] = {}
                g = group['entity'], '.'.join(key.split('.')[:-1])
                if g not in res[minute]:
                    res[minute][g] = {}
                if aggregation_type == 'weighted' and key_matches(key, sli_def['aggregation']['weight_keys']):
                    res[minute][g]['weight'] = value
                else:
                    res[minute][g]['value'] = value

    res2 = {}
    for minute, values in res.items():
        if aggregation_type == 'weighted':
            total_weight = 0
            total_value = 0
            for g, entry in values.items():
                if 'value' in entry:
                    val = entry['value']
                    weight = entry.get('weight', 1)  # In case weight was not available!

                    total_weight += weight
                    total_value += val * weight
            if total_weight != 0:
                res2[minute] = total_value / total_weight
            else:
                res2[minute] = 0
        elif aggregation_type == 'average':
            total_value = 0
            for g, entry in values.items():
                total_value += entry['value']
            res2[minute] = total_value / len(values)
        elif aggregation_type == 'sum':
            total_value = 0
            for g, entry in values.items():
                total_value += entry['value']
            res2[minute] = total_value

    for minute, value in sorted(res2.items()):
        dt = datetime.datetime.fromtimestamp(minute)
        logger.debug('{:%H:%M} {:0.2f}'.format(dt, value))

    if dsn:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute('SELECT p_id FROM zsm_data.product WHERE p_slug = %s', (product_name, ))
        row = cur.fetchone()
        if not row:
            raise Exception('Product {} not found'.format(product_name))
        product_id, = row
        logger.info('Inserting %s SLI values..', len(res2))
        for minute, val in res2.items():
            cur.execute('INSERT INTO zsm_data.service_level_indicator '
                        '(sli_product_id, sli_name, sli_timestamp, sli_value) VALUES '
                        '(%s, %s, TIMESTAMP \'epoch\' + %s * INTERVAL \'1 second\', %s) ON CONFLICT ON CONSTRAINT '
                        'service_level_indicator_pkey DO UPDATE SET sli_value = EXCLUDED.sli_value',
                        (product_id, sli_name, minute, val))
        conn.commit()

    return len(res2)


def update(sli_definition, kairosdb_url, dsn, start, time_unit):
    for product_name, product_def in sli_definition.items():
        for sli_name, sli_def in product_def.items():
            process_sli(product_name, sli_name, sli_def, kairosdb_url, start, time_unit, dsn)
