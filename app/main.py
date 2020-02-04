#!/usr/bin/env python3
import argparse
import logging
import os
import time
from datetime import datetime

import connexion
import connexion.decorators.security
import connexion.operation
import flask
import gevent
from opentracing_utils import (
    init_opentracing_tracer,
    trace_flask,
    trace_requests,
    trace_sqlalchemy,
)

from app import SERVER
from app.config import (
    APP_SESSION_SECRET,
    CACHE_THRESHOLD,
    CACHE_TYPE,
    MAX_RETENTION_DAYS,
    OPENTRACING_TRACER,
    RUN_UPDATER,
    UPDATER_INTERVAL,
)
from app.extensions import (
    cache,
    db,
    limiter,
    migrate,
    oauth,
    session,
    sqlalchemy_skip_span,
)
from app.libs.oauth import verify_oauth_with_session
from app.libs.resolver import get_operation_name, get_resource_handler

# Models
from app.resources import Indicator, Objective, Product, ProductGroup, Target  # noqa
from app.resources.sli.retention import apply_retention, cleanup_sli
from app.resources.sli.updater import update_all_indicators
from app.routes import ROUTES, process_request, rate_limit_exceeded, request_skip_span
from app.utils import DecimalEncoder

trace_requests()  # noqa


# MONKEYPATCH CONNEXION
connexion.decorators.security.verify_oauth = verify_oauth_with_session
connexion.operation.verify_oauth = verify_oauth_with_session

logger = logging.getLogger(__name__)

SWAGGER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'swagger.yaml')


def create_app(*args, **kwargs):
    connexion_app = connexion.App(__name__)
    connexion_app.app.json_encoder = DecimalEncoder

    connexion_app.app.config.from_object('app.config')

    app = connexion_app.app

    init_opentracing_tracer(OPENTRACING_TRACER)

    register_extensions(app)
    register_middleware(app)
    register_routes(connexion_app)
    register_errors(app)

    if kwargs.get('connexion_app'):
        return connexion_app

    return app


def register_extensions(app: flask.Flask) -> None:
    app.secret_key = APP_SESSION_SECRET

    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(
        app, config={'CACHE_TYPE': CACHE_TYPE, 'CACHE_THRESHOLD': CACHE_THRESHOLD}
    )
    limiter.init_app(app)
    session.init_app(app)
    oauth.init_app(app)

    app.config['SQLALCHEMY_ECHO'] = True

    trace_flask(app, operation_name=get_operation_name, skip_span=request_skip_span)
    trace_sqlalchemy(skip_span=sqlalchemy_skip_span)


def register_middleware(app: flask.Flask) -> None:
    # Add middleware processors
    app.before_request(process_request)


def register_api(connexion_app: connexion.App) -> None:
    # IMPORTANT: Add swagger api after *db* instance is ready!
    connexion_app.add_api(
        SWAGGER_PATH,
        resolver=connexion.Resolver(function_resolver=get_resource_handler),
    )


def register_routes(connexion_app: connexion.App) -> None:
    # Add extra routes
    for rule, handler in ROUTES.items():
        connexion_app.add_url_rule(rule, view_func=handler)


def register_errors(app: flask.Flask) -> None:
    app.errorhandler(429)(rate_limit_exceeded)


def run_updater(app: flask.Flask, once=False):
    with app.app_context():
        try:
            while True:
                try:
                    logger.info('Updating all indicators ...')

                    update_all_indicators(app)
                except Exception:
                    logger.exception('Updater failed!')

                if once:
                    logger.info('Completed running the updater once. Now terminating!')
                    return

                logger.info(
                    'Completed running the updater. Sleeping for {} minutes!'.format(
                        UPDATER_INTERVAL // 60
                    )
                )

                time.sleep(UPDATER_INTERVAL)
        except KeyboardInterrupt:
            logger.info('Terminating updater in response to KeyboardInterrupt!')


def run_cleanup(app: flask.Flask):
    with app.app_context():
        t_start = datetime.utcnow()

        logger.info('Cleaning up SLIs')
        cleanup_sli(app)
        logger.info('Cleaning up SLIs done')

        logger.info('Applying retention: {} days'.format(MAX_RETENTION_DAYS))
        apply_retention(app)
        logger.info('Applying retention done')

        duration = datetime.utcnow() - t_start
        logger.info(
            'Finished cleanup/retention in {} minutes'.format(duration.seconds / 60)
        )


def run():
    argp = argparse.ArgumentParser(description='Service level reports application')
    argp.add_argument(
        '--with-updater',
        dest='with_updater',
        action='store_true',
        help='Run server with updater!',
    )
    argp.add_argument(
        '-u',
        '--updater-only',
        dest='updater',
        action='store_true',
        help='Run the updater only!',
    )
    argp.add_argument(
        '-c',
        '--cleanup-only',
        dest='cleanup',
        action='store_true',
        help='Run the cleanup/retention only!',
    )
    argp.add_argument(
        '-o',
        '--once',
        dest='once',
        action='store_true',
        help='Make sure the updater runs once and exits! Only works if --updater-only is used, ignored otherwise',
    )

    args = argp.parse_args()

    connexion_app = create_app(connexion_app=True)

    if args.cleanup:
        run_cleanup(connexion_app.app)
    elif not args.updater:
        if args.with_updater or RUN_UPDATER:
            logger.info('Running SLI updater ...')
            gevent.spawn(run_updater, connexion_app.app)

        # run our standalone gevent server
        logger.info('Service level reports starting application server')

        register_api(connexion_app)

        # Start the server
        try:
            connexion_app.run(port=8080, server=SERVER)
        except KeyboardInterrupt:
            logger.info('KeyboardInterrupt ... terminating server!')
    else:
        logger.info('Running SLI updater ...')
        run_updater(connexion_app.app, args.once)


# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8080 -w app
application = create_app()


if __name__ == '__main__':
    run()
