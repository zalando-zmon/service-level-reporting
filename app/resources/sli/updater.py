import logging
import math
import os
import warnings
from datetime import datetime, timedelta

import opentracing
from flask import Flask
from gevent.pool import Pool
from opentracing_utils import extract_span_from_kwargs, trace

from app.config import MAX_QUERY_TIME_SLICE, UPDATER_CONCURRENCY
from app.extensions import db

from . import sources
from .models import Indicator, IndicatorValue, insert_indicator_value

logger = logging.getLogger(__name__)

updater_pool = Pool(UPDATER_CONCURRENCY)


def update_all_indicators(app: Flask):
    """
    Update all indicators async!
    """
    if os.environ.get("SLR_LOCAL_ENV"):
        warnings.warn("Running on local env while not setting up gevent properly!")

    for indicator in Indicator.query.all():
        try:
            if indicator.is_deleted:
                continue
            updater_pool.spawn(update_indicator, app, indicator)
        except Exception:
            logger.exception("Updater: Failed to spawn indicator updater!")

    updater_pool.join()


def update_indicator(app: Flask, indicator: Indicator):
    logger.info(
        "Updater: Updating Indicator {} values for product {}".format(
            indicator.name, indicator.product.name
        )
    )

    with app.app_context():
        try:
            count = sources.from_indicator(indicator).update_indicator_values()
            logger.info(
                'Updater: Updated {} indicator values "{}" for product "{}"'.format(
                    count, indicator.name, indicator.product.name
                )
            )
        except Exception:
            logger.exception(
                'Updater: Failed to update indicator "{}" values for product "{}"'.format(
                    indicator.name, indicator.product.name
                )
            )
