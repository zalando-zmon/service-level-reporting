from app.config import API_AUTHORIZATION

from .admin import AdminOnly
from .community import CommunityAuthorization
from .simple import Authorization


def get_authorization() -> Authorization:
    if API_AUTHORIZATION.lower() == 'community':
        return CommunityAuthorization()
    elif API_AUTHORIZATION.lower() in ('admins', 'adminsonly', 'admins-only', 'admin'):
        return AdminOnly()
    else:
        return Authorization()


__all__ = (
    'AdminOnly',
    'Authorization',
    'CommunityAuthorization',
    'get_authorization',
)
