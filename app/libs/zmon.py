import fnmatch
import logging
import requests

from datetime import datetime
from typing import Optional, Dict

import zign.api

from app.config import KAIROSDB_URL, KAIROS_QUERY_LIMIT


AGG_TYPES = ('average', 'weighted', 'sum', 'min', 'max', 'minimum', 'maximum')

logger = logging.getLogger('slo')


def key_matches(key, key_patterns):
    for pat in key_patterns:
        if fnmatch.fnmatch(key, pat):
            return True
    return False


def query_sli(sli_name: str, sli_source: dict, start: int, end: Optional[int]) -> Dict[datetime, float]:
    check_id = sli_source['check_id']
    keys = sli_source['keys']
    exclude_keys = sli_source.get('exclude_keys', [])
    aggregation_type = sli_source['aggregation']['type']

    kairosdb_metric_name = 'zmon.check.{}'.format(check_id)

    token = zign.api.get_token('zmon', ['uid'])
    headers = {'Authorization': 'Bearer {}'.format(token)}

    session = requests.Session()
    session.headers.update(headers)

    tags = {'key': keys + sli_source['aggregation'].get('weight_keys', [])}
    if sli_source.get('tags'):
        tags.update(sli_source['tags'])

    q = {
        'start_relative': {
            'value': start,
            'unit': 'minutes'
        },
        'metrics': [{
            'name': kairosdb_metric_name,
            'tags': tags,
            'limit': KAIROS_QUERY_LIMIT,
            'group_by': [{'name': 'tag', 'tags': ['entity', 'key']}]
        }]
    }

    if end:
        q['end_relative'] = {'value': end, 'unit': 'minutes'}

    # TODO: make this part smarter.
    # If we fail with 500 then may be consider graceful retries with smaller intervals!
    response = session.post(KAIROSDB_URL + '/api/v1/datapoints/query', json=q, timeout=55)
    response.raise_for_status()

    data = response.json()

    res = {}
    for result in data['queries'][0]['results']:
        if not result.get('values'):
            continue

        group = result['group_by'][0]['group']
        key = group['key']

        exclude = key_matches(key, exclude_keys)

        if not exclude:
            for ts, value in result['values']:
                # truncate to full minutes
                minute = datetime.utcfromtimestamp((ts // 60000) * 60)
                if minute not in res:
                    res[minute] = {}

                g = group['entity'], '.'.join(key.split('.')[:-1])
                if g not in res[minute]:
                    res[minute][g] = {}

                if aggregation_type == 'weighted' and key_matches(key, sli_source['aggregation']['weight_keys']):
                    res[minute][g]['weight'] = value
                else:
                    res[minute][g]['value'] = value

    result = {}
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
                result[minute] = total_value / total_weight
            else:
                result[minute] = 0
        # TODO: aggregate in Kairosdb query?!
        elif aggregation_type == 'average':
            total_value = 0
            for g, entry in values.items():
                total_value += entry['value']
            result[minute] = total_value / len(values)
        # TODO: aggregate in Kairosdb query?!
        elif aggregation_type == 'sum':
            total_value = 0
            for g, entry in values.items():
                total_value += entry['value']
            result[minute] = total_value
        elif aggregation_type in ('minimum', 'min'):
            result[minute] = min([entry['value'] for g, entry in values.items()])
        elif aggregation_type in ('maximum', 'max'):
            result[minute] = max([entry['value'] for g, entry in values.items()])

    return result
