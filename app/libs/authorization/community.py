import logging
import functools

from urllib.parse import urljoin
from typing import List, Callable

import requests
import zign.api

from connexion import request, ProblemException

from app.config import ADMINS
from app.config import API_AUTHORIZATION_COMMUNITY_URL, API_AUTHORIZATION_COMMUNITY_PREFIX
from app.utils import slugger
from app.extensions import cache, db

from .simple import Authorization


logger = logging.getLogger(__name__)


@cache.memoize(timeout=300)
def get_user_groups(username):
    try:
        token = zign.api.get_token('uid', ['uid'])
        headers = {'Authorization': 'Bearer {}'.format(token)}

        logger.debug('Retrieving groups for user: {}'.format(username))

        url = urljoin(API_AUTHORIZATION_COMMUNITY_URL, 'api/employees/{}/groups'.format(username))
        resp = requests.get(url, headers=headers, timeout=2)
        resp.raise_for_status()
        res = resp.json()

        return [r['name'] for r in res]
    except Exception:
        logger.exception('Failed to get user {} groups'.format(username))
        return []


def validate_tokeninfo(f) -> Callable:
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token_info = request.token_info
        if not token_info or token_info.get('realm') != '/employees':
            raise ProblemException(
                status=401, title='UnAuthorized', detail='Only employees are allowed to modify/create resources.')

        return f(*args, **kwargs)

    return wrapper


class CommunityAuthorization(Authorization):
    """Custom authorization based on Communities"""

    @property
    def current_user_communities(self):
        uid = request.token_info['uid']

        groups = get_user_groups(uid)

        # expected : "Function/Communities/*/COMMUNITY-NANE/ROLE"
        communities = [
            slugger(c.split('/')[-2]) for c in groups if c.startswith(API_AUTHORIZATION_COMMUNITY_PREFIX)
        ]

        return communities

    def is_admin(self) -> bool:
        uid = request.token_info['uid']
        return uid in ADMINS

    def community_match(self, product_group: str, communities: List[str]) -> bool:
        product_group_community = product_group.lower()
        if product_group.startswith('Core') and '/' in product_group:
            product_group_community = slugger(product_group.split('/')[1])

        return self.is_admin() or product_group_community in communities

    @validate_tokeninfo
    def create(self, obj: db.Model, **kwargs):
        return

    @validate_tokeninfo
    def update(self, obj: db.Model, **kwargs):
        if not self.community_match(obj.get_owner(), self.current_user_communities):
            raise ProblemException(
                status=401, title='UnAuthorized',
                detail="User is not allowed to update current resource owned by '{}'".format(obj.get_owner()))

    @validate_tokeninfo
    def delete(self, obj: db.Model, **kwargs):
        if not self.community_match(obj.get_owner(), self.current_user_communities):
            raise ProblemException(
                status=401, title='UnAuthorized',
                detail="User is not allowed to delete current resource owned by '{}'".format(obj.get_owner()))
