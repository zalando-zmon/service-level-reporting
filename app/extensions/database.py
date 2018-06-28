from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


db = SQLAlchemy()
migrate = Migrate()


def sqlalchemy_skip_span(conn, cursor, statement, parameters, context, executemany):
    return statement.lower().startswith('insert into indicatorvalue')
