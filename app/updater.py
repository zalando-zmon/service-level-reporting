import logging

import gevent

from app.handler.product import get_products
from app.handler.slo import update_service_level_objectives


def run_sli_update():
    logger = logging.getLogger('sli-update')
    while True:
        gevent.sleep(int(gevent.os.getenv('UPDATE_INTERVAL_SECONDS', 600)))
        try:
            for product in get_products():
                update_service_level_objectives(product['slug'])
        except:
            logger.exception('Failed to update SLIs')
