from urllib.parse import urljoin
from datetime import datetime

from flask import request
from flask import session as flask_session

from app.libs.resource import ResourceHandler


class APIRoot(ResourceHandler):

    @classmethod
    def get(cls, **kwargs) -> dict:
        return {
            'health_uri': urljoin(request.api_url, 'health'),
            'session_uri': urljoin(request.api_url, 'session'),
            'product_groups_uri': urljoin(request.api_url, 'product-groups'),
            'products_uri': urljoin(request.api_url, 'products'),
        }

    @classmethod
    def health(cls, **kwargs) -> dict:
        return {}, 200

    @classmethod
    def session(cls, **kwargs) -> dict:
        return {
            'username': request.user,
            'last_login': flask_session.get('last_login', datetime.now().isoformat())
        }
