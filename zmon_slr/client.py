import requests

from typing import List

from urllib.parse import urljoin


class SLRClientError(Exception):
    pass


class Client:
    def __init__(self, url: str, token: str):
        self.url = urljoin(url, 'api/')
        self.token = token

        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Bearer {}'.format(token), 'User-Agent': 'slr-cli/0.1-alpha'})

        # Load root URIs
        resp = self.session.get(self.url)
        resp.raise_for_status()
        api = resp.json()

        self.HEALTH = api['health_uri']
        self.PRODUCT_GROUPS = api['product_groups_uri']
        self.PRODUCTS = api['products_uri']

    def product_list(self, name: str=None, product_group_name: str=None, limit: int=100, q: str=None) -> List[dict]:
        params = {} if not name else {'name': name}

        if q:
            params['q'] = q

        if product_group_name:
            params['product_group'] = product_group_name

        if limit:
            params['page_size'] = limit

        res = self.session.get(self.PRODUCTS, params=params)
        res.raise_for_status()

        ps = res.json()
        return ps['data']

    def product_delete(self, product: dict) -> requests.Response:
        res = self.session.delete(product['uri'])
        res.raise_for_status()

        return res

    def product_create(self, name, product_group_uri, email=None) -> dict:
        data = {'name': name, 'product_group_uri': product_group_uri, 'email': email}

        res = self.session.post(self.PRODUCTS, json=data)
        res.raise_for_status()

        return res.json()

    def product_update(self, product: dict) -> dict:
        if 'uri' not in product:
            raise SLRClientError('Cannot determine product URI')

        res = self.session.put(product['uri'], json=product)
        res.raise_for_status()

        return res.json()

    def product_group_list(self, name: str=None, q: str=None, limit: int=100) -> List[dict]:
        params = {} if not name else {'name': name}

        if q:
            params['q'] = q

        if limit:
            params['page_size'] = limit

        res = self.session.get(self.PRODUCT_GROUPS, params=params)
        res.raise_for_status()

        pgs = res.json()
        return pgs['data']

    def product_group_get(self, uri) -> dict:
        res = self.session.get(uri)
        res.raise_for_status()

        return res.json()

    def product_group_delete(self, uri) -> requests.Response:
        res = self.session.delete(uri)
        res.raise_for_status()

        return res

    def product_group_create(self, name, department) -> dict:
        data = {
            'name': name,
            'department': department or ''
        }

        res = self.session.post(self.PRODUCT_GROUPS, json=data)
        res.raise_for_status()

        return res.json()

    def product_group_update(self, product_group: dict) -> dict:
        if 'uri' not in product_group:
            raise SLRClientError('Cannot determine product-group URI')

        res = self.session.put(product_group['uri'], json=product_group)
        res.raise_for_status()

        return res.json()

    def slo_list(self, product: dict, id=None) -> List[dict]:
        params = {}
        if id:
            params = {'id': id}

        res = self.session.get(product['product_slo_uri'], params=params)
        res.raise_for_status()

        slo = res.json()
        return slo['data']

    def slo_delete(self, slo: dict) -> requests.Response:
        res = self.session.delete(slo['uri'])
        res.raise_for_status()

        return res

    def slo_create(self, product: dict, title: str, description: str) -> dict:
        slo = {
            'title': title,
            'description': description
        }

        res = self.session.post(product['product_slo_uri'], json=slo)
        res.raise_for_status()

        return res.json()

    def slo_update(self, slo: dict) -> dict:
        if 'uri' not in slo:
            raise SLRClientError('Cannot determine slo URI')

        res = self.session.put(slo['uri'], json=slo)
        res.raise_for_status()

        return res.json()

    def target_list(self, slo: dict) -> List[dict]:
        res = self.session.get(slo['slo_targets_uri'])
        res.raise_for_status()

        slo = res.json()
        return slo['data']

    def target_get(self, uri) -> dict:
        res = self.session.get(uri)
        res.raise_for_status()

        return res.json()

    def target_delete(self, target: dict) -> requests.Response:
        res = self.session.delete(target['uri'])
        res.raise_for_status()

        return res

    def target_create(self, slo: dict, sli_uri: str, target_from: float=0.0, target_to: float=0.0) -> dict:
        target = {
            'from': target_from,
            'to': target_to,
            'sli_uri': sli_uri
        }

        res = self.session.post(slo['slo_targets_uri'], json=target)
        res.raise_for_status()

        return res.json()

    def target_update(self, target: dict) -> dict:
        if 'uri' not in target:
            raise SLRClientError('Cannot determine target URI')

        res = self.session.put(target['uri'], json=target)
        res.raise_for_status()

        return res.json()

    def sli_list(self, product: dict, name=None) -> List[dict]:
        params = {} if not name else {'name': name}

        res = self.session.get(product['product_sli_uri'], params=params)
        res.raise_for_status()

        sli = res.json()
        return sli['data']

    def sli_get(self, uri) -> dict:
        res = self.session.get(uri)
        res.raise_for_status()

        return res.json()

    def sli_delete(self, sli: dict) -> requests.Response:
        res = self.session.delete(sli['uri'])
        res.raise_for_status()

        return res

    def sli_create(self, product: dict, name: str, unit: str, source: dict) -> dict:
        sli = {
            'name': name,
            'source': source,
            'unit': unit
        }

        res = self.session.post(product['product_sli_uri'], json=sli)
        res.raise_for_status()

        return res.json()

    def sli_update(self, sli: dict) -> dict:
        if 'uri' not in sli:
            raise SLRClientError('Cannot determine sli URI')

        res = self.session.put(sli['uri'], json=sli)
        res.raise_for_status()

        return res.json()

    def sli_values(self, sli: dict, page_size=None, sli_from=None) -> List[dict]:
        params = {}
        if sli_from:
            params['from'] = sli_from
        elif page_size:
            params['page_size'] = page_size
        res = self.session.get(sli['sli_values_uri'], params=params)
        res.raise_for_status()

        values = res.json()
        return values['data']

    def sli_query(self, sli: dict, start: int, end: str=None) -> dict:
        data = {}
        if start:
            data['start'] = start
        if end:
            data['end'] = end

        res = self.session.post(sli['sli_query_uri'], json=data)
        res.raise_for_status()

        return res.json()

    def product_report(self, product: dict) -> dict:
        resp = self.session.get(product['product_reports_weekly_uri'], timeout=180)

        resp.raise_for_status()

        return resp.json()
