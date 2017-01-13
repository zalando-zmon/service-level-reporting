import os

import psycopg2.pool
from psycopg2.extras import NamedTupleCursor

database_uri = os.getenv('DATABASE_URI')
# NOTE: we can safely use SimpleConnectionPool instead of ThreadedConnectionPool as we use gevent greenlets
pool = psycopg2.pool.SimpleConnectionPool(1, 10, database_uri, cursor_factory=NamedTupleCursor)


class DatabaseConnection:
    def __enter__(self):
        self.conn = pool.getconn()
        return self.conn

    def __exit__(self, type, value, traceback):
        pool.putconn(self.conn)


# more convenient short alias
dbconn = DatabaseConnection
