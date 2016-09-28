#!/usr/bin/env python3

import collections
import colorsys
import jinja2
import os
import re
import requests
import sys
import zign.api

import plot


def title(s):
    return s.title().replace('_', ' ').replace('.', ' ')


def alarm_color(d, worst=4, saturation=0.5):
    """Return HTML alarm color value based on input value compared to possible ``worst`` value.

    :param d: value to base alarm color value on
    :param worst: upper limit for alarm input values
    :param saturation: color saturation
    :return: HTML color value string
    """

    if d is None:
        return 'auto'
    if isinstance(d, list) or isinstance(d, dict):
        d = len(d)
    factor = d * 1.0 / worst
    factor = max(0, 1.0 - factor)
    factor = factor * factor
    r, g, b = colorsys.hsv_to_rgb(factor * 0.35, saturation, .95)
    return '#%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255))


base_url = sys.argv[1]
product = sys.argv[2]

url = '{}/service-level-objectives/{}'.format(base_url, product)
resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
resp.raise_for_status()
slos = resp.json()

os.makedirs('output/{}'.format(product), exist_ok=True)

url = '{}/service-level-objectives/{}/reports/weekly'.format(base_url, product)
resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
resp.raise_for_status()
report_data = resp.json()

values_by_sli = collections.defaultdict(list)
for day, data in sorted(report_data['days'].items()):
    for sli_name, _sli_data in data.items():
        values_by_sli[sli_name].append(_sli_data['avg'])

loader = jinja2.FileSystemLoader('templates')
env = jinja2.Environment(loader=loader)

data = {
    'product': report_data['product'],
    'period': '{} - {}'.format(min(report_data['days'].keys())[:10], max(report_data['days'].keys())[:10]),
    'slos': []}

for slo in slos:
    slo['slis'] = {}
    for target in slo['targets']:
        val = sum(values_by_sli[target['sli_name']]) / len(values_by_sli[target['sli_name']])
        ok = True
        if target['to'] and val > target['to']:
            ok = False
        if target['from'] and val < target['from']:
            ok = False
        slo['slis'][target['sli_name']] = {
                'avg': '{:.2f} {}'.format(val, target['unit']),
                'ok': ok
                }
    slo['data'] = []
    breaches_by_sli = collections.defaultdict(int)
    for day, day_data in sorted(report_data['days'].items()):
        slis = {}
        for sli, sli_data in day_data.items():
            breaches_by_sli[sli] += sli_data['breaches']
            classes = set()
            if sli_data['breaches']:
                classes.add('orange')
            unit = ''
            for target in slo['targets']:
                if target['sli_name'] == sli:
                    unit = target['unit']
                    if target['to'] and sli_data['avg'] > target['to']:
                        classes.add('red')
                    elif target['from'] and sli_data['avg'] < target['from']:
                        classes.add('red')

            if sli_data['count'] < 1400:
                classes.add('not-enough-samples')

            slis[sli] = sli_data
            slis[sli]['unit'] = unit
            slis[sli]['classes'] = classes
        slo['data'].append({'caption': day[5:10], 'slis': slis})
    slo['breaches'] = max(breaches_by_sli.values())

    fn = 'output/{}/chart-{}-{}-{}.png'.format(product, slo['id'], min(report_data['days'].keys()), max(report_data['days'].keys()))
    fn = re.sub('[^/0-9a-zA-Z.-]', '', fn)
    plot.plot(base_url, product, slo['id'], fn)
    slo['chart'] = os.path.basename(fn)
    data['slos'].append(slo)

env.filters['sli_title'] = title
env.filters['alarm_color'] = alarm_color
template = env.get_template('slr.tpl')
template.stream(**data).dump('output/{}/index.html'.format(product))
