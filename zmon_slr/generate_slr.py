#!/usr/bin/env python3

import datetime
import logging
import os
import sys
import time
from math import ceil

import jinja2

from zmon_slr.client import Client
from zmon_slr.plot import plot

RETRY_SLEEP = 10
MAX_RETRIES = 10

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)


def call_and_retry(fn, *args, **kwargs):
    """Call `fn` and retry in case of API exception."""
    count = 0

    while True:
        try:
            return fn(*args, **kwargs)
        except Exception:
            if count < MAX_RETRIES:
                logger.info('Retrying {} for args: {}'.format(fn, args))
                time.sleep(RETRY_SLEEP)
                count += 1
                continue
            raise


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
    reverse = False
    for entry in sorted(os.listdir(output_dir)):
        if '.' not in entry:
            entry.split()
            if not entry.startswith('20'):
                # leaf directory with actual report
                generate_directory_index(
                    os.path.join(output_dir, entry), os.path.join(path, entry)
                )
                dirs.append((entry, entry))
            else:
                from_date, to_date = entry.split('-')
                start = datetime.datetime.strptime(from_date, '%Y%m%d')
                end = datetime.datetime.strptime(to_date, '%Y%m%d')
                dirs.append(
                    (
                        '{} - {}'.format(
                            start.strftime('%A, %d %B %Y'), end.strftime('%A, %d %B %Y')
                        ),
                        entry,
                    )
                )
                reverse = True

    if reverse:
        dirs.reverse()
    data = {'path': path, 'dirs': dirs}

    loader = jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')
    )
    env = jinja2.Environment(loader=loader)
    template = env.get_template('directory_index.html')
    template.stream(**data).dump(os.path.join(output_dir, 'index.html'))


def get_classes_for_aggregate(aggregate):
    classes = set()

    if not aggregate["healthy"]:
        classes.add("red")
    elif aggregate["breaches"]:
        classes.add("orange")
    else:
        classes.add("ok")

    if aggregate["count"] and aggregate["count"] < 1400:
        classes.add("not-enough-samples")

    return classes


def format_aggregate_value(aggregate):
    return (
        "-"
        if aggregate['aggregate'] is None
        else f"{aggregate['aggregate']:.2f} {aggregate['unit']}"
    )


def parse_report_timestamp(timestamp):
    return datetime.datetime.strptime(timestamp[:10], '%Y-%m-%d')


def generate_weekly_report(client: Client, product: dict, output_dir: str) -> None:
    report_data = call_and_retry(client.product_report, product)

    product_group = report_data['product_group_slug']

    period_from = parse_report_timestamp(report_data['timerange']['start'])
    period_to = parse_report_timestamp(report_data['timerange']['end'])
    period_days = ceil(report_data['timerange']['delta_seconds'] / 86400)

    period_id = f"{period_from:%Y%m%d}-{period_to:%Y%m%d}"
    report_dir = os.path.join(output_dir, product_group, product['slug'], period_id)
    os.makedirs(report_dir, exist_ok=True)

    loader = jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')
    )
    env = jinja2.Environment(loader=loader)

    context = {
        'product': {
            'name': report_data['product_name'],
            'product_group_name': report_data['product_group_name'],
        },
        'period': f"{period_from:%Y-%m-%d} - {period_to:%Y-%m-%d}",
        'now': datetime.datetime.utcnow(),
        'slos': [],
    }

    for slo in report_data['slo']:
        no_data = set(target['sli_name'] for target in slo['targets'])
        unhealthy_days = set()
        data = []
        for timestamp, day_data in slo["days"].items():
            caption = parse_report_timestamp(timestamp).strftime("%a %m-%d")

            day_slis = {}
            for sli_name, aggregate in day_data.items():
                sli_data = aggregate.copy()

                if not sli_data["healthy"]:
                    unhealthy_days.add(caption)

                sli_data["classes"] = get_classes_for_aggregate(sli_data)
                sli_data["aggregate"] = format_aggregate_value(sli_data)

                if sli_name == "requests":
                    sli_data['total'] = int(sli_data['avg'] * sli_data['count'] * 60)

                day_slis[sli_name] = sli_data
                no_data.discard(sli_name)

            data.append({"caption": caption, "slis": day_slis})

        slis = {}
        for name, aggregate in slo["total"].items():
            slis[name] = {
                "aggregate": format_aggregate_value(aggregate),
                "ok": aggregate["healthy"],
                "unit": aggregate["unit"],
            }

        filename = os.path.join(report_dir, 'chart-{}.png'.format(slo['id']))
        chart = os.path.basename(filename)
        plot(client, product, slo['id'], filename)

        context['slos'].append(
            {
                "no_data": no_data,
                "unhealthy_days": len(unhealthy_days),
                "unhealthy_days_percentage": (len(unhealthy_days) / period_days) * 100,
                "data": data,
                "slis": slis,
                "chart": chart,
                "title": slo["title"],
                "description": slo["description"],
            }
        )

    env.filters['sli_title'] = title
    env.filters['human_time'] = human_time

    template = env.get_template('slr-weekly.html')
    template.stream(**context).dump(os.path.join(report_dir, 'index.html'))

    generate_directory_index(output_dir)
