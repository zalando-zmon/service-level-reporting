#!/usr/bin/env python3

import os
import json
import numbers
import subprocess

import click
import requests
import zign.api

from clickclick import AliasedGroup, Action, error, warning, fatal_error
from zmon_cli.client import Zmon

from zmon_slr.client import Client, SLRClientError
from zmon_slr.generate_slr import generate_weekly_report


DEFAULT_CONFIG_FILE = '~/.zmon-slr.yaml'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
SLR_TOKEN = os.environ.get('SLR_TOKEN')

AGG_TYPES = ('average', 'weighted', 'sum', 'min', 'max', 'minimum', 'maximum')


def get_config_data(config_file=DEFAULT_CONFIG_FILE):
    fn = os.path.expanduser(config_file)
    data = {}

    try:
        if os.path.exists(fn):
            with open(fn) as fd:
                data = json.load(fd)
        else:
            warning('No configuration file found at [{}]'.format(config_file))

            data = set_config_file()

            if not data:
                error('Failed to configure ZMON SLR cli.')

    except Exception as e:
        fatal_error(e)

    return data


def set_config_file(config_file=DEFAULT_CONFIG_FILE):
    while True:
        url = click.prompt('Please enter the SLR base URL (e.g. https://slo-metrics.example.com)')

        with Action('Checking {}..'.format(url)):
            requests.get(url, timeout=5, allow_redirects=False)

        zmon_url = click.prompt('Please enter the ZMON URL (e.g. https://demo.zmon.io)')

        with Action('Checking {}..'.format(zmon_url)):
            requests.get(zmon_url, timeout=5, allow_redirects=False)
            break

    data = {
        'url': url,
        'zmon_url': zmon_url,
    }

    fn = os.path.expanduser(config_file)
    with Action('Writing configuration to {}..'.format(fn)):
        with open(fn, 'w') as fd:
            json.dump(data, fd)

    return data


def flatten(structure, key='', path='', flattened=None):
    '''
    >>> flatten({})
    {}
    >>> flatten({'a': {'b': {'c': ['d', 'e']}}})
    {'a.b.c': ['d', 'e']}
    >>> sorted(flatten({'a': {'b': 'c'}, 'd': 'e'}).items())
    [('a.b', 'c'), ('d', 'e')]
    '''
    path = str(path)
    key = str(key)

    if flattened is None:
        flattened = {}
    if not isinstance(structure, dict):
        flattened[((path + '.' if path else '')) + key] = structure
    else:
        for new_key, value in structure.items():
            flatten(value, new_key, '.'.join(filter(None, [path, key])), flattened)
    return flattened


def get_client(config):
    token = SLR_TOKEN if SLR_TOKEN else zign.api.get_token('uid', ['uid'])
    return Client(config['url'], token)


@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cli(ctx):
    """
    Service Level Reporting command line interface
    """
    config = get_config_data()

    ctx.obj = config


@cli.command('configure')
@click.pass_context
def configure(ctx):
    """Configure CLI"""
    set_config_file()


########################################################################################################################
# PRODUCT GROUP
########################################################################################################################
@cli.group('group', cls=AliasedGroup)
@click.pass_obj
def product_group(obj):
    """SLR product groups"""
    pass


@product_group.command('list')
@click.pass_obj
def product_group_list(obj):
    """List all product groups"""
    client = get_client(obj)

    res = client.product_group_list()

    print(json.dumps(res, indent=4))


@product_group.command('get')
@click.argument('name')
@click.pass_obj
def product_group_get(obj, name):
    """List all product groups"""
    client = get_client(obj)

    pgs = client.product_group_list(name)
    if not pgs:
        fatal_error('Product group {} does not exist'.format(name))

    print(json.dumps(pgs[0], indent=4))


@product_group.command('create')
@click.argument('name')
@click.argument('department')
@click.pass_obj
def product_group_create(obj, name, department):
    """Create a new product group"""
    client = get_client(obj)

    with Action('Creating product_group: {}'.format(name), nl=True):
        pg = client.product_group_create(name, department)

        print(json.dumps(pg, indent=4))


@product_group.command('update')
@click.argument('name')
@click.option('--new-name', '-n', required=False, help='Product group new name.')
@click.option('--department', '-d', required=False, help='Product group new department.')
@click.pass_obj
def product_group_update(obj, name, new_name, department):
    """Update product group"""
    client = get_client(obj)

    pgs = client.product_group_list(name)
    if not pgs:
        fatal_error('Product group {} does not exist'.format(name))

    with Action('Updating product_group: {}'.format(name), nl=True):
        pg = pgs[0]
        if new_name:
            pg['name'] = new_name
        if department:
            pg['department'] = department

        pg = client.product_group_update(pg)

        print(json.dumps(pg, indent=4))


@product_group.command('delete')
@click.argument('name')
@click.pass_obj
def product_group_delete(obj, name):
    """Delete a product group"""
    client = get_client(obj)

    with Action('Deleting product_group: {}'.format(name), nl=True):
        pgs = client.product_group_list(name)

        client.product_group_delete(pgs[0]['uri'])


########################################################################################################################
# PRODUCT
########################################################################################################################
@cli.group('product', cls=AliasedGroup)
@click.pass_obj
def product(obj):
    """SLR products"""
    pass


@product.command('list')
@click.option('--product-group-name', '-p', required=False, type=str, help='Filter products by product group name.')
@click.pass_obj
def product_list(obj, product_group_name):
    """List all products"""
    client = get_client(obj)

    res = client.product_list(product_group_name=product_group_name)

    print(json.dumps(res, indent=4))


@product.command('get')
@click.argument('name')
@click.pass_obj
def product_get(obj, name):
    """Get product"""
    client = get_client(obj)

    p = client.product_list(name=name)

    if not p:
        fatal_error('Product does not exist')

    print(json.dumps(p[0], indent=4))


@product.command('create')
@click.argument('name')
@click.argument('product_group_name')
@click.option('--email', '-e', required=False, help='Product email. Could be used in notifications.')
@click.pass_obj
def product_create(obj, name, product_group_name, email):
    """Create new product"""
    client = get_client(obj)

    with Action('Creating product: {}'.format(name), nl=True) as act:
        try:
            pgs = client.product_group_list(name=product_group_name)
            if not pgs:
                act.fatal_error('Product group does not exist!')

            pg = pgs[0]

            p = client.product_create(name, product_group_uri=pg['uri'], email=email)

            print(json.dumps(p, indent=4))
        except SLRClientError as e:
            act.error(e)


@product.command('update')
@click.argument('name')
@click.option('--new-name', '-n', required=False, help='Product new name.')
@click.option('--new-email', '-e', required=False, help='Product new email.')
@click.option('--product-group-name', '-p', required=False, help='Product new product group name.')
@click.pass_obj
def product_update(obj, name, new_name, new_email, product_group_name):
    """Update product"""
    client = get_client(obj)

    ps = client.product_list(name)
    if not ps:
        fatal_error('Product {} does not exist'.format(name))

    with Action('Updating product: {}'.format(name), nl=True):
        p = ps[0]
        if new_name:
            p['name'] = new_name

        if new_email:
            p['email'] = new_email

        if product_group_name:
            pgs = client.product_group_list(name=product_group_name)
            if not pgs:
                fatal_error('Product group {} does not exist'.format(product_group_name))
            p['product_group_uri'] = pgs[0]['uri']

        p = client.product_update(p)

        print(json.dumps(p, indent=4))


@product.command('delete')
@click.argument('name')
@click.pass_obj
def product_delete(obj, name):
    """Delete a product"""
    client = get_client(obj)

    with Action('Deleting product: {}'.format(name), nl=True):
        p = client.product_list(name=name)
        if not p:
            fatal_error('Product {} does not exist!'.format(name))

        client.product_delete(p[0])


########################################################################################################################
# SLO
########################################################################################################################
def validate_slo(slo: dict, act: Action):
    if not slo.get('title'):
        act.error('Field "title" is missing in SLO definition.')

    for target in slo.get('targets', []):
        validate_target(target, act)


@cli.group('slo', cls=AliasedGroup)
@click.pass_obj
def slo(obj):
    """Service level objectives"""
    pass


@slo.command('list')
@click.argument('product_name')
@click.pass_obj
def slo_list(obj, product_name):
    """List all SLOs for a product"""
    client = get_client(obj)

    p = client.product_list(name=product_name)
    if not p:
        fatal_error('Product {} does not exist'.format(product_name))

    res = client.slo_list(p[0])

    print(json.dumps(res, indent=4))


@slo.command('create')
@click.argument('product_name')
@click.option('--title', '-t', help='SLO title')
@click.option('--description', '-d', default='', help='SLO description')
@click.option('--slo-file', '-f', type=click.File('r'), help='SLO definition JSON file. File can include Targets list')
@click.pass_obj
def slo_create(obj, product_name, title, description, slo_file):
    """
    Create SLO. If SLO file is used, then --title and --description will be ignored.
    """
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    with Action('Creating SLO for product: {}'.format(product_name), nl=True) as act:
        if slo_file:
            slo = json.load(slo_file)
        else:
            slo = {'title': title, 'description': description}

        validate_slo(slo, act)

        if not act.errors:
            new_slo = client.slo_create(product, slo['title'], slo.get('description', ''))

            print(json.dumps(new_slo, indent=4))

            for target in slo.get('targets', []):
                t = client.target_create(new_slo, target['sli_uri'], target_from=target['from'], target_to=target['to'])
                act.ok('Created a new target')
                print(json.dumps(t, indent=4))


@slo.command('update')
@click.argument('product_name')
@click.argument('slo_id')
@click.option('--title', '-t', help='SLO title')
@click.option('--description', '-d', default='', help='SLO description')
@click.option('--slo-file', '-f', type=click.File('r'), help='SLO definition JSON file. Targets list will be ignored.')
@click.pass_obj
def slo_update(obj, product_name, slo_id, title, description, slo_file):
    """
    Update SLO for a product. All targets will be ignored if specified in SLO definitions.
    Updating targets can be achieved via "target" command.
    """
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slo = client.slo_list(product, id=slo_id)
    if not slo:
        fatal_error('SLO {} does not exist'.format(slo_id))

    slo = slo[0]

    with Action('Updating SLO {} for product {}'.format(slo_id, slo['product_name']), nl=True) as act:
        if slo_file:
            slo = json.load(slo_file)
            slo['uri'] = slo['uri']
        else:
            if title:
                slo['title'] = title
            if description:
                slo['description'] = description

        validate_slo(slo, act)

        if not act.errors:
            slo = client.slo_update(slo)

            print(json.dumps(slo, indent=4))


@slo.command('delete')
@click.argument('product_name')
@click.argument('slo_id')
@click.pass_obj
def slo_delete(obj, product_name, slo_id):
    """Delete SLO for certain product"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slo = client.slo_list(product, id=slo_id)
    if not slo:
        fatal_error('SLO {} does not exist'.format(slo_id))

    slo = slo[0]

    if product['name'] != slo['product_name']:
        fatal_error('Cannot delete SLO {} as it does not belong to product {}'.format(slo_id, product_name))

    with Action('Deleting SLO: {}'.format(slo['uri']), nl=True):
        client.slo_delete(slo)


########################################################################################################################
# TARGET
########################################################################################################################
def validate_target(target, act):
    if 'sli_uri' not in target:
        act.error('Field "sli_uri" is missing in SLO target definition.')
    if 'from' not in target or target['from'] is not None and not isinstance(target['from'], numbers.Number):
        act.error('Numeric field "from" is missing in SLO target definition.')
    if 'to' not in target or target['to'] is not None and not isinstance(target['to'], numbers.Number):
        act.error('Numeric field "to" is missing in SLO target definition.')


@cli.group('target', cls=AliasedGroup)
@click.pass_obj
def target(obj):
    """Service level objectives Targets"""
    pass


@target.command('list')
@click.argument('product_name')
@click.argument('slo_id')
@click.pass_obj
def target_list(obj, product_name, slo_id):
    """List all Targets for a SLO"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slo = client.slo_list(product, id=slo_id)
    if not slo:
        fatal_error('SLO {} does not exist'.format(slo_id))

    slo = slo[0]

    res = client.target_list(slo)

    print(json.dumps(res, indent=4))


@target.command('create')
@click.argument('product_name')
@click.argument('slo_id')
@click.option('--sli-name', '-s', help='SLI name')
@click.option('--target-from', '-r', type=float, help='Target "from" value')
@click.option('--target-to', '-t', type=float, help='Target "to" value')
@click.option('--target-file', '-f', type=click.File('r'), help='Target definition JSON file.')
@click.pass_obj
def target_create(obj, product_name, slo_id, sli_name, target_from, target_to, target_file):
    """
    Create Target. If target-file is used, then other options are ignored.
    """
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slo = client.slo_list(product, id=slo_id)
    if not slo:
        fatal_error('SLO {} does not exist'.format(slo_id))

    slo = slo[0]

    product = client.product_list(name=slo['product_name'])[0]

    sli = client.sli_list(product=product, name=sli_name)
    if not sli or not sli_name:
        fatal_error('SLI {} does not exist'.format(sli_name))
    sli = sli[0]

    with Action(
            'Creating Targets for SLO: {} for product: {}'.format(slo['title'], slo['product_name']), nl=True) as act:
        if target_file:
            target = json.load(target_file)
        else:
            target = {'sli_uri': sli['uri'], 'from': target_from, 'to': target_to}

        validate_target(target, act)

        if not act.errors:
            t = client.target_create(slo, target['sli_uri'], target_from=target.get('from'), target_to=target.get('to'))

            print(json.dumps(t, indent=4))


@target.command('update')
@click.argument('target_uri')
@click.option('--sli-name', '-s', help='SLI name')
@click.option('--target-from', '-r', type=float, help='Target "from" value')
@click.option('--target-to', '-t', type=float, help='Target "to" value')
@click.option('--target-file', '-f', type=click.File('r'), help='Target definition JSON file.')
@click.pass_obj
def target_update(obj, target_uri, sli_name, target_from, target_to, target_file):
    """Update Target for a product SLO."""
    client = get_client(obj)

    target = client.target_get(target_uri)
    if not target:
        fatal_error('Target {} does not exist'.format(target_uri))

    product = client.product_list(name=target['product_name'])[0]

    sli = client.sli_list(product=product, name=sli_name)
    if not sli:
        fatal_error('SLI {} does not exist'.format(sli_name))
    sli = sli[0]

    with Action('Updating Target {} for product {}'.format(target_uri, target['product_name']), nl=True) as act:
        if target_file:
            target = json.load(target_file)
        else:
            if sli_name:
                target['sli_uri'] = sli['uri']
            if target_from:
                target['from'] = target_from
            if target_to:
                target['to'] = target_to

        validate_target(target, act)

        if not act.errors:
            target = client.target_update(target)

            print(json.dumps(target, indent=4))


@target.command('delete')
@click.argument('product_name')
@click.argument('target_uri')
@click.pass_obj
def target_delete(obj, product_name, target_uri):
    """Delete Target for certain product"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    target = client.target_get(target_uri)

    if product['name'] != target['product_name']:
        fatal_error('Cannot delete Target {} as it does not belong to product {}'.format(target_uri, product_name))

    with Action('Deleting Target: {}'.format(target_uri), nl=True):
        client.target_delete(target)


########################################################################################################################
# SLI
########################################################################################################################
def validate_sli_source(config, source, ignore_keys=False):
    if 'zmon_url' not in config:
        config = set_config_file()

    zmon = Zmon(config['zmon_url'], token=zign.api.get_token('uid', ['uid']))

    check_id = int(source['check_id'])

    try:
        check = zmon.get_check_definition(check_id)
    except Exception:
        raise SLRClientError('Check definition {} does not seem to exist!'.format(check_id))

    alerts = zmon.get_alert_definitions()
    filtered = [alert for alert in alerts if alert['check_definition_id'] == check_id]
    if not filtered:
        raise SLRClientError(
            'Check definition has no alerts. Please create an Alert for this check on ZMON {}'.format(
                zmon.check_definition_url(check))
        )

    if ignore_keys:
        return

    keys = [k for k in source['keys'] if '.*' not in k]
    if not keys:
        # Do not validate keys if we have wildcards
        return

    sli_exists = False
    sample_data = set()
    for alert in filtered:
        if sli_exists:
            break

        alert_data = zmon.get_alert_data(alert['id'])

        values = {v['entity']: v['results'][0]['value'] for v in alert_data if len(v['results'])}

        for entity, data in values.items():
            if type(data) is dict:
                flattened = flatten(data)

                data_keys = flattened.keys()
                sample_data.update(list(data_keys))

                if not (set(keys) - set(data_keys)):
                    sli_exists = True
                    break

    if not sli_exists:
        raise SLRClientError(
            'Some SLI keys do not exist. Please check the data returned from the check and the corresponding keys '
            'in the SLI source. Found the following keys returned from check {}: {}'.format(
                check_id, set(sample_data)))


def validate_sli(obj: dict, sli: dict, act: Action):
    if 'name' not in sli or not sli['name']:
        act.error('Field "name" is missing in SLI definition.')

    if 'unit' not in sli or not sli['unit']:
        act.error('Field "unit" is missing in SLI definition.')

    if 'source' not in sli:
        act.error('Field "source" is missing in SLI definition.')

    source = sli.get('source', {})

    required = {'aggregation', 'check_id', 'keys'}
    missing = set(required) - set(source.keys())

    # checking SLI source structure
    if missing:
        act.error('Fields {} are missing in SLI source definition.'.format(missing))

    if 'keys' not in missing and not source.get('keys'):
        act.error('Field "keys" value is missing in SLI source definition.')

    # Checking aggregation sanity
    aggregation = source.get('aggregation', {})
    agg_type = aggregation.get('type')
    if 'aggregation' not in missing:
        if not agg_type or agg_type not in AGG_TYPES:
            act.error('Field "type" is missing in SLI source aggregation. Valid values are: {}'.format(AGG_TYPES))

        if agg_type == 'weighted' and not aggregation.get('weight_keys'):
            act.error('Field "weight_keys" is missing in SLI source aggregation for type "weighted".')

    if 'check_id' not in missing and 'keys' not in missing and source['keys']:
        try:
            validate_sli_source(obj, source)
        except SLRClientError as e:
            act.fatal_error(e)


@cli.group('sli', cls=AliasedGroup)
@click.pass_obj
def sli(obj):
    """Service level indicators"""
    pass


@sli.command('get')
@click.argument('product_name')
@click.argument('name')
@click.pass_obj
def sli_get(obj, product_name, name):
    """Get SLI for a product by name"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    slis = client.sli_list(product[0], name=name)
    if not slis:
        fatal_error('SLI {} does not exist'.format(name))

    print(json.dumps(slis[0], indent=4))


@sli.command('list')
@click.argument('product_name')
@click.pass_obj
def sli_list(obj, product_name):
    """List SLIs for a product"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    res = client.sli_list(product[0])

    print(json.dumps(res, indent=4))


@sli.command('create')
@click.argument('product_name')
@click.argument('sli_file', type=click.File('r'))
@click.pass_obj
def sli_create(obj, product_name, sli_file):
    """Create SLI for a product"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    with Action('Creating SLI for product: {}'.format(product_name), nl=True) as act:
        sli = json.load(sli_file)

        validate_sli(obj, sli, act)

        if not act.errors:
            res = client.sli_create(product, sli['name'], sli['unit'], sli['source'])
            print(json.dumps(res, indent=4))


@sli.command('update')
@click.argument('product_name')
@click.argument('name')
@click.argument('sli_file', type=click.File('r'))
@click.pass_obj
def sli_update(obj, product_name, name, sli_file):
    """Update SLI for a product"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slis = client.sli_list(product, name)
    if not slis:
        fatal_error('SLI {} does not exist'.format(name))

    with Action('Updating SLI {} for product: {}'.format(name, product_name), nl=True) as act:
        sli = json.load(sli_file)

        validate_sli(obj, sli, act)

        if not act.errors:
            sli['uri'] = slis[0]['uri']
            s = client.sli_update(sli)

            print(json.dumps(s, indent=4))


@sli.command('delete')
@click.argument('product_name')
@click.argument('name')
@click.pass_obj
def sli_delete(obj, product_name, name):
    """Delete SLI for a product"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slis = client.sli_list(product, name)
    if not slis:
        fatal_error('SLI {} does not exist'.format(name))

    with Action('Deleting SLI: {} for product {}'.format(name, product['name']), nl=True) as act:
        try:
            client.sli_delete(slis[0])
        except SLRClientError as e:
            act.fatal_error(e)


@sli.command('values')
@click.argument('product_name')
@click.argument('name')
@click.option('--count', '-c', type=int, help='Number of SLI values returned')
@click.pass_obj
def sli_values(obj, product_name, name, count):
    """List SLI values"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slis = client.sli_list(product, name)
    if not slis:
        fatal_error('SLI {} does not exist'.format(name))

    res = client.sli_values(slis[0], page_size=count)

    print(json.dumps(res, indent=4))


@sli.command('query')
@click.argument('product_name')
@click.argument('name')
@click.option('--start', '-s', required=True, type=int, help='Relative start in minutes.')
@click.option('--end', '-e', required=False, type=int, help='Relative end in minutes.')
@click.pass_obj
def sli_query(obj, product_name, name, start, end):
    """Update SLI values"""
    client = get_client(obj)

    if start and end and start <= end:
        fatal_error('Relative "end" should be less than "start"')

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    slis = client.sli_list(product, name)
    if not slis:
        fatal_error('SLI {} does not exist'.format(name))

    res = client.sli_query(slis[0], start, end)

    print(json.dumps(res, indent=4))


########################################################################################################################
# REPORTS
########################################################################################################################
@cli.group('report', cls=AliasedGroup)
@click.pass_obj
def report(obj):
    """Service level reports"""
    pass


@report.command('create')
@click.argument('product_name')
@click.option('--output-dir', '-o', help='Output directory', default='output')
@click.pass_obj
def report_create(obj, product_name, output_dir):
    """Create report for a product"""
    client = get_client(obj)

    product = client.product_list(name=product_name)
    if not product:
        fatal_error('Product {} does not exist'.format(product_name))

    product = product[0]

    try:
        subprocess.check_output(['which', 'gnuplot'])
    except subprocess.CalledProcessError:
        fatal_error('Missing system dependency. Please install *gnuplot* system package!')

    with Action('Creating report for product: {}'.format(product_name), nl=True):
        generate_weekly_report(client, product, output_dir)


def main():
    try:
        cli()
    except requests.HTTPError as e:
        detail = ''
        try:
            detail = e.response.json()['detail']
        except Exception:
            pass

        fatal_error('HTTP error: {} - {} - {}'.format(e.response.status_code, e.response.reason, detail))
