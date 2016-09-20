#!/usr/bin/env python3

import click
import requests
import zign.api


@click.command()
@click.option('--kairosdb-url')
@click.option('--metric-name')
@click.option('--key', '-k', multiple=True)
def cli(kairosdb_url, metric_name, key):
    # do stuff

    token = zign.api.get_token('zmon', ['uid'])
    headers = {'Authorization': 'Bearer {}'.format(token)}

    session = requests.Session()
    session.headers.update(headers)

    q = {
            'start_relative': {
                'value': 5,
                'unit': 'minutes'
            },
            'metrics': [{
                'name': metric_name,
                'tags': {'key': key},
                'group_by': [{'name': 'tag', 'tags': ['entity', 'key']}]
            }]
        }

    response = session.post(kairosdb_url + '/api/v1/datapoints/query', json=q)
    response.raise_for_status()

    data = response.json()
    for result in data['queries'][0]['results']:
        print(result['group_by'])



if __name__ == '__main__':
    cli()
