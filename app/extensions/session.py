import dateutil.parser

from datetime import datetime, timedelta

from flask import session as flask_session
from flask_session import Session


def get_token_info():
    expiry = flask_session.get('token_expiry')

    now = datetime.utcnow()

    if expiry and dateutil.parser.parse(expiry) > now:
        return {
            'access_token': flask_session.get('access_token'),
            'user': flask_session.get('uid'),
            'token_expiry': flask_session.get('token_expiry'),
        }

    return {}


def set_token_info(token_info):
    if (flask_session.get('user') == token_info.get('uid') and
            flask_session.get('access_token') == token_info['access_token']):
        return

    flask_session['user'] = token_info.get('uid', '')
    flask_session['access_token'] = token_info['access_token']

    expires = datetime.utcnow() + timedelta(minutes=int(token_info.get('expires_in', 1)))
    flask_session['token_expiry'] = expires.isoformat()


session = Session()
