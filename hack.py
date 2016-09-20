#!/usr/bin/env python3

import click
import fnmatch
import psycopg2
import requests
import yaml
import zign.api


def key_matches(key, key_patterns):
    for pat in key_patterns:
        if fnmatch.fnmatch(key, pat):
            return True
    return False


def process_sli(product_name, sli_name, sli_def, kairosdb_url, start, time_unit, dsn):
    check_id = sli_def['check_id']
    keys = sli_def['keys']
    exclude_keys = sli_def.get('exclude_keys', [])
    aggregation_type = sli_def['aggregation']['type']

    kairosdb_metric_name = 'zmon.check.{}'.format(check_id)

    token = zign.api.get_token('zmon', ['uid'])
    headers = {'Authorization': 'Bearer {}'.format(token)}

    session = requests.Session()
    session.headers.update(headers)

    q = {
            'start_relative': {
                'value': start,
                'unit': time_unit
            },
            'metrics': [{
                'name': kairosdb_metric_name,
                'tags': {'key': keys + sli_def['aggregation'].get('weight_keys', [])},
                'group_by': [{'name': 'tag', 'tags': ['entity', 'key']}]
            }]
        }

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
                if 'weight' in entry and 'value' in entry:
                    total_weight += entry['weight']
                    total_value += entry['value'] * entry['weight']
            res2[minute] = total_value / total_weight
        elif aggregation_type == 'sum':
            total_value = 0
            for g, entry in values.items():
                total_value += entry['value']
            res2[minute] = total_value

    print(sli_name)
    print(res2)

    if dsn:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        for minute, val in res2.items():
            cur.execute('INSERT INTO foo (sli_name, sli_value) VALUES (%s, %s)', (sli_name, val))
        conn.commit()


@click.command()
@click.argument('sli_definition', type=click.File('rb'))
@click.option('--kairosdb-url')
@click.option('--start', type=int, default=5)
@click.option('--time-unit', default='minutes')
@click.option('--dsn')
def cli(sli_definition, kairosdb_url, dsn, start, time_unit):
    sli_definition = yaml.safe_load(sli_definition)

    for product_name, product_def in sli_definition.items():
        for sli_name, sli_def in product_def.items():
            process_sli(product_name, sli_name, sli_def, kairosdb_url, start, time_unit, dsn)



if __name__ == '__main__':
    cli()
