import logging

from connexion import request, ProblemException

from app.config import ADMINS
from app.extensions import db
from app.libs.authorization.simple import Authorization


logger = logging.getLogger(__name__)


class AdminOnly(Authorization):
    """Only Admins can delete objects"""

    def delete(self, obj: db.Model, **kwargs) -> None:
        user = request.user if hasattr(request, 'user') else None

        logger.debug('User {} deleting resource {}'.format(user, obj))

        if not user or user not in ADMINS:
            raise ProblemException(
                status=401, title='UnAuthorized', detail='Only Admins are allowed to delete this resource!')
