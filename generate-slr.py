#!/usr/bin/env python3

import collections
import datetime
import os

import click
import jinja2
import requests
import zign.api

import plot


def title(s):
    return s.title().replace('_', ' ').replace('.', ' ')


def human_time(minutes):
    days = minutes // (60 * 24)
    remainder = minutes % (60 * 24)
    hours = remainder // 60
    minutes = remainder % 60
    s = []

    if days:
        s.append('{} day(s)'.format(days))
    if hours:
        s.append('{} hour(s)'.format(hours))
    if minutes:
        s.append('{} minute(s)'.format(minutes))

    return ' '.join(s)


def generate_directory_index(output_dir, path='/'):
    dirs = []
    for entry in sorted(os.listdir(output_dir)):
        if '.' not in entry:
            dirs.append(entry)
            if not entry.startswith('20'):
                # leaf directory with actual report
                generate_directory_index(os.path.join(output_dir, entry), os.path.join(path, entry))

    data = {'path': path, 'dirs': dirs}

    loader = jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates'))
    env = jinja2.Environment(loader=loader)
    template = env.get_template('directory_index.html')
    template.stream(**data).dump(os.path.join(output_dir, 'index.html'))


def generate_weekly_report(base_url, product, output_dir):
    url = '{}/service-level-objectives/{}/reports/weekly'.format(base_url, product)
    resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
    resp.raise_for_status()
    report_data = resp.json()

    # TODO: should use pg_slug from PostgreSQL database (but we don't return it right now)
    product_group = report_data['product']['product_group_name'].lower()

    period_from = min(report_data['service_level_objectives'][0]['days'].keys())[:10]
    period_to = max(report_data['service_level_objectives'][0]['days'].keys())[:10]

    period_id = '{}-{}'.format(period_from.replace('-', ''), period_to.replace('-', ''))

    report_dir = os.path.join(output_dir, product_group, product, period_id)
    os.makedirs(report_dir, exist_ok=True)

    values_by_sli = collections.defaultdict(list)
    for slo in report_data['service_level_objectives']:
        for day, data in sorted(slo['days'].items()):
            for sli_name, _sli_data in data.items():
                values_by_sli[sli_name].append(_sli_data['avg'])

    loader = jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates'))
    env = jinja2.Environment(loader=loader)

    data = {
        'product': report_data['product'],
        'period': '{} - {}'.format(period_from, period_to),
        'slos': []}

    for slo in report_data['service_level_objectives']:
        slo['slis'] = {}

        for target in slo['targets']:
            val = (sum(values_by_sli[target['sli_name']]) / len(values_by_sli[target['sli_name']]) if
                   len(values_by_sli[target['sli_name']]) > 0 else None)
            ok = True
            if val is not None and target['to'] and val > target['to']:
                ok = False
            if val is not None and target['from'] and val < target['from']:
                ok = False
            slo['slis'][target['sli_name']] = {
                'avg': '-' if val is None else '{:.2f} {}'.format(val, target['unit']),
                'ok': ok
            }

        slo['data'] = []
        breaches_by_sli = collections.defaultdict(int)
        counts_by_sli = collections.defaultdict(int)
        for day, day_data in sorted(slo['days'].items()):
            slis = {}
            for sli, sli_data in day_data.items():
                breaches_by_sli[sli] += sli_data['breaches']
                counts_by_sli[sli] += sli_data['count']
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

                if sli == 'requests':
                    # interpolate total number of requests per day from average per sec
                    sli_data['total'] = int(sli_data['avg'] * sli_data['count'] * 60)
                slis[sli] = sli_data
                slis[sli]['unit'] = unit
                slis[sli]['classes'] = classes
            dt = datetime.datetime.strptime(day[:10], '%Y-%m-%d')
            dow = dt.strftime('%a')
            slo['data'].append({'caption': '{} {}'.format(dow, day[5:10]), 'slis': slis})
        slo['breaches'] = max(breaches_by_sli.values())
        slo['count'] = max(counts_by_sli.values())

        fn = os.path.join(report_dir, 'chart-{}.png'.format(slo['id']))
        plot.plot(base_url, product, slo['id'], fn)
        slo['chart'] = os.path.basename(fn)
        data['slos'].append(slo)

    data['now'] = datetime.datetime.utcnow()

    env.filters['sli_title'] = title
    env.filters['human_time'] = human_time
    template = env.get_template('slr-weekly.html')
    template.stream(**data).dump(os.path.join(report_dir, 'index.html'))

    generate_directory_index(output_dir)


@click.command()
@click.argument('base_url')
@click.argument('product')
@click.option('--output-dir', '-o', help='Output directory', default='output')
def cli(base_url, product, output_dir):
    generate_weekly_report(base_url, product, output_dir)


if __name__ == '__main__':
    cli()
