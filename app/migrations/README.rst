=====================
ALEMBIC DB Migrations
=====================

Initialization
--------------

Note: This step is already done!


.. code-block:: bash

    export FLASK_APP=app/main.py

    flask db init -d app/migrations
    flask db migrate -d app/migrations


Apply migrations
----------------

Assuming Postgresql is running.


.. code-block:: bash

    flask db upgrade -d app/migrations



Model change
------------

Creating new migration for a model change.


.. code-block:: bash

    export FLASK_APP=app/__init__.py

    flask db migrate -d app/migrations

