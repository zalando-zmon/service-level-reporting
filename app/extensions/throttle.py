from flask import session, request
from flask_limiter import Limiter


def get_limiter_key():
    # First, from request
    if hasattr(request, 'token_info'):
        return request.token_info['access_token']

    # Next, session token
    token = session.get('access_token')
    if token:
        return token

    # Next, from auth headers
    auth_headers = request.headers.get('Authorization', '')
    if auth_headers:
        _, token = auth_headers.split()

        if token:
            return token

    # Next, forwarded for ip
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for

    # Last, from remote address
    return request.remote_addr


limiter = Limiter(key_func=get_limiter_key)
