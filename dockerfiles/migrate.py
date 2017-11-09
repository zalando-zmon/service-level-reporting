#!/usr/bin/env python3

import os
import sys
import time
import logging
import subprocess

from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy_utils.functions import database_exists, create_database


MAX_RETRIES = 5

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

logger.addHandler(logging.StreamHandler(sys.stdout))


def upgrade(path):
    try:
        result = subprocess.check_output(['flask', 'db', 'upgrade', '-d', path], stderr=subprocess.STDOUT)
        for r in result.splitlines():
            print(r)
    except subprocess.CalledProcessError as e:
        return e.returncode

    return 0


def create_user(database_uri, user, password):
    engine = create_engine(database_uri)

    conn = engine.connect()

    try:
        conn.execute("CREATE USER {} WITH PASSWORD '{}';".format(user, password))
    except ProgrammingError:
        logger.error('SQL error creating user')
    except Exception:
        logger.exception('Error creating user')

    try:
        conn.execute(
            ('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES,'
             ' TRIGGER ON TABLES TO {user};').format(user=user)
        )
        conn.execute(
            ('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {user};')
            .format(user=user)
        )

        conn.execute(
            ('GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public '
             'TO {};').format(user)
        )
        conn.execute(
            ('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {};').format(user)
        )
    except ProgrammingError as e:
        logger.error('SQL error assigning permissions: {}'.format(e))
    except Exception:
        logger.exception('Error assigning permissions')


def main():
    retries = MAX_RETRIES

    database_uri = os.environ.get('DATABASE_URI')
    if not database_uri:
        logger.error('Migration cannot proceed. Please specify full DATABASE_URI.')
        sys.exit(1)

    database_user = os.environ.get('DATABASE_USER')
    database_password = os.environ.get('DATABASE_PASSWORD')
    if not database_user or not database_password:
        logger.error('Migration cannot proceed. Please specify full DATABASE_USER & DATABASE_PASSWORD for limited '
                     'privilege application user!')
        sys.exit(1)

    migration_path = os.environ.get('DATABASE_MIGRATIONS', '/app/migrations')

    logger.info('Preparing for migration...')

    time.sleep(1)

    while retries:
        try:
            logger.info('Creating database ...')

            if not database_exists(database_uri):
                create_database(database_uri)

                logger.info('Database created!')
            else:
                logger.info('Database exists!')

            logger.info('Upgrading database ...')

            if upgrade(migration_path):
                logger.error('Failed to upgrade')
                sys.exit(1)

            logger.info('Creating and assigning user permissions')
            create_user(database_uri, database_user, database_password)

            logger.info('Done!')

            sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            logger.error(e)
            retries -= 1
            time.sleep(2)

    logger.error('Failed to migrate')
    sys.exit(1)


if __name__ == '__main__':
    main()
