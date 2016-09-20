#!/usr/bin/env python3

import click
import psycopg2
import requests
import zign.api


@click.command()
@click.option('--kairosdb-url')
@click.option('--check-id', type=int)
@click.option('--sli-name')
@click.option('--start', type=int, default=5)
@click.option('--time-unit', default='minutes')
@click.option('--key', '-k', multiple=True)
@click.option('--exclude-key', '-x', multiple=True)
@click.option('--aggregation')
@click.option('--dsn')
@click.option('--weight-pattern', default='rate')
def cli(kairosdb_url, check_id, sli_name, start, time_unit, key, exclude_key, aggregation, dsn, weight_pattern):
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
                'tags': {'key': key},
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
        exclude = False
        for excl in exclude_key:
            if excl in key:
                exclude = True
        if not exclude:
            for ts, value in result['values']:
                # truncate to full minutes
                minute = (ts // 60000) * 60
                if minute not in res:
                    res[minute] = {}
                g = group['entity'], '.'.join(key.split('.')[:-1])
                if g not in res[minute]:
                    res[minute][g] = {}
                if aggregation == 'weighted' and weight_pattern in key.lower():
                    res[minute][g]['weight'] = value
                else:
                    res[minute][g]['value'] = value

    print(res)
    res2 = {}
    for minute, values in res.items():
        if aggregation == 'weighted':
            total_weight = 0
            total_value = 0
            for g, entry in values.items():
                if 'weight' in entry and 'value' in entry:
                    total_weight += entry['weight']
                    total_value += entry['value'] * entry['weight']
            res2[minute] = total_value / total_weight
        elif aggregation == 'sum':
            total_value = 0
            for g, entry in values.items():
                total_value += entry['value']
            res2[minute] = total_value

    print(res2)

    if dsn:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        for minute, val in res2.items():
            cur.execute('INSERT INTO foo (sli_name, sli_value) VALUES (%s, %s)', (sli_name, val))
        conn.commit()



if __name__ == '__main__':
    cli()
