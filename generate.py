#!/usr/bin/env python3

import collections
import jinja2
import os
import requests
import sys
import zign.api

import plot

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
    print(day)
    print(data)

loader = jinja2.FileSystemLoader('templates')
env = jinja2.Environment(loader=loader)

data = {
    'product': product,
    'period': '{} - {}'.format(min(report_data.keys()), max(report_data.keys())),
    'slos': []}

for slo in slos:
    slo['slis'] = {}
    for target in slo['targets']:
        slo['slis'][target['sli_name']] = '{:.2f}{}'.format(sum(values_by_sli[target['sli_name']]) / len(values_by_sli[target['sli_name']]), target['unit'])
    slo['data'] = []
    breaches_by_sli = collections.defaultdict(int)
    for day, day_data in sorted(report_data.items()):
        slis = {}
        for sli, sli_data in day_data.items():
            breaches_by_sli[sli] += sli_data['breaches']
            flag = ''
            if sli_data['breaches']:
                flag = 'orange'
            slis[sli] = {'value': sli_data['avg'], 'flag': flag}
        slo['data'].append({'caption': day[5:10], 'slis': slis})
    slo['breaches'] = max(breaches_by_sli.values())

    fn = 'output/{}.png'.format(slo['id'])
    plot.plot(base_url, product, slo['id'], fn)
    slo['chart'] = os.path.basename(fn)
    data['slos'].append(slo)

template = env.get_template('slr.tpl')
os.makedirs('output', exist_ok=True)
template.stream(**data).dump('output/slr.html')
