#!/usr/bin/env python3

import collections
import jinja2
import os
import re
import requests
import sys
import zign.api

import plot


def title(s):
    return s.title().replace('_', ' ').replace('.', ' ')

base_url = sys.argv[1]
product = sys.argv[2]

url = '{}/service-level-objectives/{}'.format(base_url, product)
resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
resp.raise_for_status()
slos = resp.json()

url = '{}/service-level-objectives/{}/reports/weekly'.format(base_url, product)
resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
resp.raise_for_status()
report_data = resp.json()

values_by_sli = collections.defaultdict(list)
for day, data in sorted(report_data.items()):
    for sli_name, _sli_data in data.items():
        values_by_sli[sli_name].append(_sli_data['avg'])

loader = jinja2.FileSystemLoader('templates')
env = jinja2.Environment(loader=loader)

data = {
    'product': product,
    'period': '{} - {}'.format(min(report_data.keys()), max(report_data.keys())),
    'slos': []}

for slo in slos:
    slo['slis'] = {}
    for target in slo['targets']:
        slo['slis'][target['sli_name']] = '{:.2f} {}'.format(sum(values_by_sli[target['sli_name']]) / len(values_by_sli[target['sli_name']]), target['unit'])
    slo['data'] = []
    breaches_by_sli = collections.defaultdict(int)
    for day, day_data in sorted(report_data.items()):
        slis = {}
        unit = ''
        for sli, sli_data in day_data.items():
            breaches_by_sli[sli] += sli_data['breaches']
            flag = ''
            if sli_data['breaches']:
                flag = 'orange'
            for target in slo['targets']:
                if target['sli_name'] == sli:
                    unit = target['unit']
                    if target['to'] and sli_data['avg'] > target['to']:
                        flag = 'red'
                    elif target['from'] and sli_data['avg'] < target['from']:
                        flag = 'red'

            slis[sli] = {'value': sli_data['avg'], 'flag': flag, 'unit': unit}
        slo['data'].append({'caption': day[5:10], 'slis': slis})
    slo['breaches'] = max(breaches_by_sli.values())

    fn = 'output/chart-{}-{}-{}-{}.png'.format(product, slo['id'], min(report_data.keys()), max(report_data.keys()))
    fn = re.sub('[^/0-9a-zA-Z-]', '', fn)
    plot.plot(base_url, product, slo['id'], fn)
    slo['chart'] = os.path.basename(fn)
    data['slos'].append(slo)

env.filters['sli_title'] = title
template = env.get_template('slr.tpl')
os.makedirs('output', exist_ok=True)
template.stream(**data).dump('output/slr.html')
