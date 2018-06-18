import os
import functools
import logging
import textwrap

import requests
from flask import request
from flask import session as flask_session
from flask_oauthlib.client import OAuth, OAuthRemoteApp

from connexion.exceptions import OAuthProblem, OAuthResponseProblem, OAuthScopeProblem

from opentracing_utils import extract_span_from_flask_request, trace

from app.config import CREDENTIALS_DIR, AUTHORIZE_URL, ACCESS_TOKEN_URL
from app.extensions import set_token_info, cache


logger = logging.getLogger('connexion.api.security')

# use connection pool for OAuth tokeninfo
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
session = requests.Session()
session.mount('http://', adapter)
session.mount('https://', adapter)


def get_auth_app(oauth: OAuth):
    auth = OAuthRemoteAppWithRefresh(
        oauth,
        'auth',
        request_token_url=None,
        access_token_method='POST',
        access_token_url=ACCESS_TOKEN_URL,
        authorize_url=AUTHORIZE_URL
    )

    return auth


class OAuthRemoteAppWithRefresh(OAuthRemoteApp):
    '''Same as flask_oauthlib.client.OAuthRemoteApp, but always loads client credentials from file.'''

    def __init__(self, oauth, name, **kwargs):
        # constructor expects some values, so make it happy..
        kwargs['consumer_key'] = 'not-needed-here'
        kwargs['consumer_secret'] = 'not-needed-here'
        OAuthRemoteApp.__init__(self, oauth, name, **kwargs)

    def refresh_credentials(self):
        with open(os.path.join(CREDENTIALS_DIR, 'authcode-client-id')) as fd:
            self._consumer_key = fd.read().strip()
        with open(os.path.join(CREDENTIALS_DIR, 'authcode-client-secret')) as fd:
            self._consumer_secret = fd.read().strip()

    @property
    def consumer_key(self):
        self.refresh_credentials()
        return self._consumer_key

    @property
    def consumer_secrect(self):
        self.refresh_credentials()
        return self._consumer_secret


########################################################################################################################
# OVERRIDE CONNEXION OAUTH2
# Session aware API authentication
########################################################################################################################
def verify_oauth_with_session(token_info_url, allowed_scopes, function):
    """
    Decorator to verify oauth

    :param token_info_url: Url to get information about the token
    :type token_info_url: str
    :param allowed_scopes: Set with scopes that are allowed to access the endpoint
    :type allowed_scopes: set
    :type function: types.FunctionType
    :rtype: types.FunctionType
    """

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        logger.debug("%s Oauth verification...", request.url)

        authorization = request.headers.get('Authorization')  # type: str

        # check if session authenticated user
        is_authenticated = flask_session.get('is_authenticated')
        user = flask_session.get('user')
        token = flask_session.get('access_token')

        if not authorization and not token:
            logger.info("... No auth provided. Aborting with 401.")
            raise OAuthProblem(description='No authorization token provided')

        if not all([user, is_authenticated, token]):
            if not token:
                try:
                    _, token = authorization.split()  # type: str, str
                except ValueError:
                    raise OAuthProblem(description='Invalid authorization header')

            token_info = fetch_token_info(token_info_url, token)

            user_scopes = set(token_info['scope'])

            logger.debug("... Scopes required: %s", allowed_scopes)
            logger.debug("... User scopes: %s", user_scopes)

            if not allowed_scopes <= user_scopes:
                logger.info(textwrap.dedent("""
                            ... User scopes (%s) do not match the scopes necessary to call endpoint (%s).
                             Aborting with 403.""").replace('\n', ''),
                            user_scopes, allowed_scopes)
                raise OAuthScopeProblem(
                    description='Provided token doesn\'t have the required scope',
                    required_scopes=allowed_scopes,
                    token_scopes=user_scopes
                )

            logger.info("... Token authenticated.")

            request.user = token_info.get('uid')
            request.token_info = token_info

            set_token_info(token_info)

        return function(*args, **kwargs)

    return wrapper


@cache.memoize(60)
@trace(span_extractor=extract_span_from_flask_request, tags={'oauth2': True})
def fetch_token_info(token_info_url, token):

    logger.info("... Getting token from %s", token_info_url)

    token_request = session.get(token_info_url, headers={'Authorization': 'Bearer {}'.format(token)}, timeout=2)

    logger.debug("... Token info (%d): %s", token_request.status_code, token_request.text)

    if not token_request.ok:
        raise OAuthResponseProblem(
            description='Provided oauth token is not valid',
            token_response=token_request
        )

    return token_request.json()
