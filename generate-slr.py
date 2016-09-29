#!/usr/bin/env python3

import collections
import os

import click
import jinja2
import requests
import zign.api

import plot


def title(s):
    return s.title().replace('_', ' ').replace('.', ' ')


def generate_weekly_report(base_url, product, output_dir):
    url = '{}/service-level-objectives/{}'.format(base_url, product)
    resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
    resp.raise_for_status()
    slos = resp.json()

    url = '{}/service-level-objectives/{}/reports/weekly'.format(base_url, product)
    resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
    resp.raise_for_status()
    report_data = resp.json()

    # TODO: should use pg_slug from PostgreSQL database (but we don't return it right now)
    product_group = report_data['product']['product_group_name'].lower()

    period_id = '{}-{}'.format(min(report_data['days'].keys())[:10].replace('-', ''), max(report_data['days'].keys())[:10].replace('-', ''))

    report_dir = os.path.join(output_dir, product_group, product, period_id)
    os.makedirs(report_dir, exist_ok=True)

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

                if not classes:
                    classes.add('ok')

                if sli_data['count'] < 1400:
                    classes.add('not-enough-samples')

                slis[sli] = sli_data
                slis[sli]['unit'] = unit
                slis[sli]['classes'] = classes
            slo['data'].append({'caption': day[5:10], 'slis': slis})
        slo['breaches'] = max(breaches_by_sli.values())

        fn = os.path.join(report_dir, 'chart-{}.png'.format(slo['id']))
        plot.plot(base_url, product, slo['id'], fn)
        slo['chart'] = os.path.basename(fn)
        data['slos'].append(slo)

    env.filters['sli_title'] = title
    template = env.get_template('slr.tpl')
    template.stream(**data).dump(os.path.join(report_dir, 'index.html'))


@click.command()
@click.argument('base_url')
@click.argument('product')
@click.option('--output-dir', '-o', help='Output directory', default='output')
def cli(base_url, product, output_dir):
    generate_weekly_report(base_url, product, output_dir)


if __name__ == '__main__':
    cli()
