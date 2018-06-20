import logging

from datetime import datetime, timedelta
from flask import Flask

from app.config import MAX_RETENTION_DAYS
from app.extensions import db

from .models import IndicatorValue, Indicator


logger = logging.getLogger(__name__)


def cleanup_sli(app: Flask):
    with app.app_context():
        try:
            t_start = datetime.utcnow()
            count = Indicator.query.filter_by(is_deleted=True).delete()
            db.session.commit()
            duration = datetime.utcnow() - t_start
            logger.info('Deleted SLIs: {} in {} minutes'.format(count, duration.seconds / 60))
        except Exception:
            logger.exception('Failed to cleanup SLIs!')


def apply_retention(app: Flask):
    now = datetime.utcnow()
    retention = now - timedelta(days=MAX_RETENTION_DAYS)

    with app.app_context():
        try:
            t_start = datetime.utcnow()
            count = IndicatorValue.query.filter(IndicatorValue.timestamp <= retention).delete()
            db.session.commit()
            duration = datetime.utcnow() - t_start
            logger.info('Deleted SLI values: {} in {} minutes'.format(count, duration.seconds / 60))
        except Exception:
            logger.exception('Failed to apply retention: {} - {}'.format(MAX_RETENTION_DAYS, retention))
