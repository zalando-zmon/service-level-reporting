#!/usr/bin/env python3

import os
import json

import click
import requests
import zign.api


from urllib.parse import urljoin

from clickclick import AliasedGroup, Action, error, warning
from zmon_cli.client import Zmon


DEFAULT_CONFIG_FILE = '~/.zmon-slr.yaml'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

AGG_TYPES = ('average', 'weighted', 'sum', 'minimum', 'maximum')


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
        error(e)

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


def validate_sli(config, data_source):
    if 'zmon_url' not in config:
        config = set_config_file()

    zmon = Zmon(config['zmon_url'], token=zign.api.get_token('uid', ['uid']))

    check_id = int(data_source['definition']['check_id'])

    try:
        zmon.get_check_definition(check_id)
    except:
        raise SLRClientError('Check definition {} does not seem to exist!'.format(check_id))

    alerts = zmon.get_alert_definitions()
    filtered = [alert for alert in alerts if alert['check_definition_id'] == check_id]
    if not filtered:
        raise SLRClientError('Check definition has no alerts. Please create an Alert for this check on ZMON.')

    keys = data_source['definition']['keys']
    sli_exists = False
    sample_data = {}
    for alert in filtered:
        if sli_exists:
            break
        alert_data = zmon.get_alert_data(alert['id'])

        values = {v['entity']: v['results'][0]['value'] for v in alert_data if len(v['results'])}

        for entity, data in values.items():
            if type(data) is dict:
                data_keys = data.keys()
                if data_keys:
                    sample_data = data_keys
                if not (set(keys) - set(data_keys)):
                    sli_exists = True
                    break

    if not sli_exists:
        raise SLRClientError(
            'Some SLI keys do not exist. Please check the data returned from the check and the corresponding keys '
            'in the data-source. Found the following keys returned from check {}: {}'.format(
                check_id, set(sample_data)))


def get_client(config):
    return Client(config['url'], zign.api.get_token('uid', ['uid']))


class SLRClientError(Exception):
    pass


class Client:
    PRODUCT_GROUPS = 'product-groups'
    PRODUCTS = 'products'
    SLO = 'service-level-objectives'
    DATA_SOURCE = 'data-sources'
    SLI = 'service-level-indicators'

    def __init__(self, url, token):
        self.url = url
        self.token = token

        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Bearer {}'.format(token), 'User-Agent': 'SLR-SLI/0.1-alpha'})

    def endpoint(self, *args, trailing_slash=False, base_url=None):
        parts = list(args)

        # Ensure trailing slash!
        if trailing_slash:
            parts.append('')

        url = self.url if not base_url else base_url

        return urljoin(url, '/'.join(str(p).strip('/') for p in parts))

    def product_list(self):
        res = self.session.get(self.endpoint(self.PRODUCTS))
        res.raise_for_status()

        return res.json()

    def product_delete(self, name):
        res = self.session.delete(self.endpoint(self.PRODUCTS, name))
        res.raise_for_status()

        return res

    def product_create(self, name, product_group):
        data = {'name': name, 'product_group': product_group}

        pgs = self.product_group_list()
        match = [pg for pg in pgs if pg['slug'] == product_group]
        if not match:
            raise SLRClientError('Product group "{}" does not exist!'.format(product_group))

        res = self.session.post(self.endpoint(self.PRODUCTS), json=data)
        res.raise_for_status()

        return res

    def product_group_list(self):
        res = self.session.get(self.endpoint(self.PRODUCT_GROUPS))
        res.raise_for_status()

        return res.json()

    def product_group_delete(self, name):
        res = self.session.delete(self.endpoint(self.PRODUCT_GROUPS, name))
        res.raise_for_status()

        return res

    def product_group_create(self, name, department):
        data = {
            'name': name,
            'department': department
        }

        res = self.session.post(self.endpoint(self.PRODUCT_GROUPS), json=data)
        res.raise_for_status()

        return res

    def slo_list(self, product):
        res = self.session.get(self.endpoint(self.SLO, product))
        res.raise_for_status()

        return res.json()

    def slo_delete(self, product, id):
        slos = self.slo_list(product)

        match = [slo for slo in slos if slo.get('id') == int(id)]

        if not match:
            raise SLRClientError('SLO with ID: {} does not belong to Product: {}'.format(id, product))

        res = self.session.delete(self.endpoint(self.SLO, id))
        res.raise_for_status()

        return res

    def slo_create(self, product, slo):
        res = self.session.post(self.endpoint(self.SLO, product), json=slo)
        res.raise_for_status()

        return res

    def data_source_list(self, product):
        res = self.session.get(self.endpoint(self.DATA_SOURCE, product))
        res.raise_for_status()

        return res.json()

    def data_source_get(self, product, id):
        pass

    def data_source_create(self, product, data_source):
        res = self.session.post(self.endpoint(self.DATA_SOURCE, product), json=data_source)
        res.raise_for_status()

        return res

    def data_source_delete(self, product, sli_name):
        res = self.session.delete(self.endpoint(self.DATA_SOURCE, product, sli_name))
        res.raise_for_status()

        return res

    def sli_values(self, product, sli_name):
        res = self.session.get(self.endpoint(self.SLI, product, sli_name))
        res.raise_for_status()

        return res.json()

    def sli_update(self, product, sli_name, start=None, end=None):
        data = {}
        if start:
            data['start'] = start
        if end:
            data['end'] = end

        res = self.session.post(self.endpoint(self.SLI, product, sli_name, 'update'), json=data)
        res.raise_for_status()

        return res.json()


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


@product_group.command('create')
@click.argument('name')
@click.argument('department')
@click.pass_obj
def product_group_create(obj, name, department):
    """Create a new product group"""
    client = get_client(obj)

    with Action('Creating product_group: {}'.format(name), nl=True):
        client.product_group_create(name, department)


@product_group.command('delete')
@click.argument('name')
@click.pass_obj
def product_group_delete(obj, name):
    """Delete a product group"""
    client = get_client(obj)

    with Action('Deleting product_group: {}'.format(name), nl=True):
        client.product_group_delete(name)


########################################################################################################################
# PRODUCT
########################################################################################################################
@cli.group('product', cls=AliasedGroup)
@click.pass_obj
def product(obj):
    """SLR products"""
    pass


@product.command('list')
@click.pass_obj
def product_list(obj):
    """List all products"""
    client = get_client(obj)

    res = client.product_list()

    print(json.dumps(res, indent=4))


@product.command('create')
@click.argument('name')
@click.argument('product_group')
@click.pass_obj
def product_create(obj, name, product_group):
    """Create new product"""
    client = get_client(obj)

    with Action('Creating product: {}'.format(name), nl=True) as act:
        try:
            client.product_create(name, product_group)
        except SLRClientError as e:
            act.error(e)


@product.command('delete')
@click.argument('name')
@click.pass_obj
def product_delete(obj, name):
    """Delete a product"""
    client = get_client(obj)

    with Action('Deleting product: {}'.format(name), nl=True):
        client.product_delete(name)


########################################################################################################################
# SLO
########################################################################################################################
@cli.group('slo', cls=AliasedGroup)
@click.pass_obj
def slo(obj):
    """Service level objectives"""
    pass


@slo.command('list')
@click.argument('product')
@click.pass_obj
def slo_list(obj, product):
    """List all SLOs for a product"""
    client = get_client(obj)

    res = client.slo_list(product)

    print(json.dumps(res, indent=4))


@slo.command('create')
@click.argument('product')
@click.argument('slo_file', type=click.File('r'))
@click.pass_obj
def slo_create(obj, product, slo_file):
    """Create SLO"""
    client = get_client(obj)

    with Action('Creating SLO for product: {}'.format(product), nl=True) as act:
        slo = json.load(slo_file)

        if 'title' not in slo:
            act.error('Field "title" is missing in SLO definition.')

        if 'targets' not in slo:
            act.error('Field "targets" is missing in SLO definition.')

        for target in slo.get('targets', []):
            if 'sli_name' not in target:
                act.error('Field "sli_name" is missing in SLO definition target.')

        if not act.errors:
            client.slo_create(product, slo)


@slo.command('delete')
@click.argument('product')
@click.argument('id')
@click.pass_obj
def slo_delete(obj, product, id):
    """Delete SLO for certain product"""
    client = get_client(obj)

    with Action('Deleting SLO: {}'.format(id), nl=True) as act:
        try:
            client.slo_delete(product, id)
        except SLRClientError as e:
            act.fatal_error(e)


########################################################################################################################
# DATA SOURCE
########################################################################################################################
@cli.group('data-source', cls=AliasedGroup)
@click.pass_obj
def data_source(obj):
    """Data sources"""
    pass


@data_source.command('list')
@click.argument('product')
@click.pass_obj
def data_source_list(obj, product):
    """List data source for a product"""
    client = get_client(obj)

    res = client.data_source_list(product)

    print(json.dumps(res, indent=4))


@data_source.command('create')
@click.argument('product')
@click.argument('data_source_file', type=click.File('r'))
@click.pass_obj
def data_source_create(obj, product, data_source_file):
    """Create data source for a product"""
    client = get_client(obj)

    with Action('Creating data source for product: {}'.format(product), nl=True) as act:
        data_source = json.load(data_source_file)

        if 'sli_name' not in data_source:
            act.error('Field "sli_name" is missing in data-source definition.')

        if 'definition' not in data_source:
            act.error('Field "definition" is missing in data-source definition.')

        definition = data_source.get('definition', {})

        required = {'aggregation', 'check_id', 'keys'}
        missing = set(required) - set(definition.keys())

        # checking definition structure
        if missing:
            act.error('Fields {} are missing in data-source definition.'.format(missing))

        if 'keys' not in missing and not definition.get('keys', []):
            act.error('Field "keys" value is missing in data-source definition.')

        # Checking aggregation sanity
        aggregation = definition.get('aggregation', {})
        agg_type = aggregation.get('type')
        if 'aggregation' not in missing:
            if not agg_type or agg_type not in AGG_TYPES:
                act.error('Field "type" is missing in data-source aggregation. Valid values are: {}'.format(AGG_TYPES))

            if agg_type == 'weighted' and not aggregation.get('weight_keys'):
                act.error('Field "weight_keys" is missing in data-source aggregation for type "weighted".')

        if 'check_id' not in missing and 'keys' not in missing and definition['keys']:
            try:
                validate_sli(obj, data_source)
            except SLRClientError as e:
                act.fatal_error(e)

        if not act.errors:
            client.data_source_create(product, data_source)


@data_source.command('delete')
@click.argument('product')
@click.argument('sli_name')
@click.pass_obj
def data_source_delete(obj, product, sli_name):
    """Delete data source for a product"""
    client = get_client(obj)

    with Action('Deleting data source for SLI: {}'.format(sli_name), nl=True) as act:
        try:
            client.data_source_delete(product, sli_name)
        except SLRClientError as e:
            act.fatal_error(e)


########################################################################################################################
# SLI
########################################################################################################################
@cli.group('sli', cls=AliasedGroup)
@click.pass_obj
def sli(obj):
    """Service level indicators"""
    pass


@sli.command('list')
@click.argument('product')
@click.argument('sli_name')
@click.pass_obj
def sli_list(obj, product, sli_name):
    """List SLI values"""
    client = get_client(obj)

    res = client.sli_values(product, sli_name)

    print(json.dumps(res, indent=4))


@sli.command('update')
@click.argument('product')
@click.argument('sli_name')
@click.option('--start', '-s', required=False, type=int, help='Relative start in minutes.')
@click.option('--end', '-e', required=False, type=int, help='Relative end in minutes.')
@click.pass_obj
def sli_update(obj, product, sli_name, start, end):
    """Update SLI values"""
    client = get_client(obj)

    if start and end and start <= end:
        error('Relative "end" should be less than "start"')
        return

    res = client.sli_update(product, sli_name, start=start, end=end)

    print(json.dumps(res, indent=4))


if __name__ == '__main__':
    try:
        cli()
    except requests.HTTPError:
        pass
