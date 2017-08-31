#!/usr/bin/env python3
from urllib.parse import urljoin, urlparse
from datetime import datetime

import zign.api

from flask import request, redirect
from flask import session as flask_session

from app.libs.oauth import get_auth_app
from app.config import APP_URL, OAUTH2_ENABLED, PRESHARED_TOKEN

from app.extensions import set_token_info, oauth


LOGIN_AUTHORIZATION = '/login/authorized'

# OAUTH setup
auth = get_auth_app(oauth)
oauth.remote_apps['auth'] = auth


def get_safe_redirect_uri(next_uri, default=''):
    redirect_uri = urljoin(APP_URL, next_uri)

    if urlparse(redirect_uri).netloc == urlparse(APP_URL).netloc:
        return redirect_uri

    return urljoin(APP_URL, default)


def health():
    return 'OK'


def login():
    # TODO: do not proceed to login if user has an authenticated session.
    next_uri = request.args.get('next', '/')
    flask_session['next_uri'] = next_uri

    redirect_uri = urljoin(APP_URL, LOGIN_AUTHORIZATION)

    if not OAUTH2_ENABLED:
        return redirect(redirect_uri)

    return auth.authorize(callback=redirect_uri)


def logout():
    # TODO: only using POST?!
    flask_session.pop('access_token', None)
    flask_session.pop('is_authenticated', None)
    return redirect(urljoin(APP_URL, '/'))


def authorized():
    if not OAUTH2_ENABLED:
        token_info = {'access_token': PRESHARED_TOKEN or zign.api.get_token('uid', ['uid'])}
    else:
        resp = auth.authorized_response()
        if resp is None:
            return 'Access denied: reason={} error={}'.format(request.args['error'], request.args['error_description'])

        if not isinstance(resp, dict):
            return 'Invalid OAUTH response'

        token_info = resp

    set_token_info(token_info)
    flask_session['is_authenticated'] = True  # Session authenticated user
    flask_session['last_login'] = datetime.now().isoformat()

    next_uri = flask_session.pop('next_uri', '/')
    redirect_uri = get_safe_redirect_uri(next_uri, default='/')

    return redirect(redirect_uri)


ROUTES = {
    '/health': health,
    '/login': login,
    LOGIN_AUTHORIZATION: authorized,
    '/logout': logout,
}
