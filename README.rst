====================
ZMON SRE SLO Metrics
====================

**WORK IN PROGRESS**

Calculate SLI/SLO metrics using ZMON's KairosDB timeseries database.

Idea:

* Retrieve metrics such as latencies and error counts from KairosDB
* Aggregate metrics, weighted by requests/s
* Push metrics truncated to full minute timestamps into PostgreSQL
* Generate reliabilty reports (weekly, monthly, ..)

.. code-block:: bash

    $ docker run -d -p 5432:5432 postgres:9.5
    $ cat schema.sql | psql -h localhost -U postgres
    $ cat sample_data.sql | psql -h localhost -U postgres
    $ export DATABASE_URI='host=localhost user=postgres'
    $ export KAIROSDB_URL=https://kairosdb.example.org
    $ sudo pip3 install -r requirements.txt
    $ ./app.py

Configuration parameters:

``OAUTH2_ACCESS_TOKENS_URL``
    Token endpoint URL.
``CREDENTIALS_DIR``
    Folder with OAuth application credentials (``client.json`` and ``user.json``).
``DATABASE_URI``
    PostgreSQL database connection string.
``KAIROSDB_URL``
    KairosDB base URL.
