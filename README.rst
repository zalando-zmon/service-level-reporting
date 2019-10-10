============================
ZMON Service Level Reporting
============================

**WORK IN PROGRESS**

Calculate SLI/SLO metrics using ZMON's KairosDB timeseries database.

Idea:

* Retrieve metrics such as latencies and error counts from KairosDB
* Aggregate metrics, weighted by requests/s
* Push metrics truncated to full minute timestamps into PostgreSQL
* Generate reliability reports (weekly, monthly, ..)


Server local setup
==================

Development
-----------

Prepare the database

.. code-block:: bash

    docker run --name slo-pg -d -p 5432:5432 postgres:9.5
    echo 'CREATE DATABASE slr' | psql -h localhost -U postgres
    export DATABASE_URI=postgresql://postgres@localhost/slr
    export KAIROSDB_URL=https://kairosdb.example.org

Run migration

.. code-block:: bash

    export FLASK_APP=app/main.py
    export SLR_LOCAL_ENV=true
    pip3 install -r requirements.txt
    flask db upgrade -d app/migrations/

Run the server

.. code-block:: bash

    python3 -m app


Configuration parameters:

``OAUTH2_ACCESS_TOKENS_URL``
    Token endpoint URL.
``CREDENTIALS_DIR``
    Folder with OAuth application credentials (``client.json`` and ``user.json``).
``DATABASE_URI``
    PostgreSQL database connection string.
``KAIROSDB_URL``
    KairosDB base URL.


Docker compose
--------------

You can deploy a server environment with ``docker-compose``

.. code-block:: bash

    $ docker-compose up


Generating Reports
==================

You will need to install ``gnuplot`` as a system dependency. Running the following command will generate a report for the specified project in ``output`` directory. You will need ``zmon-slr`` CLI to be installed (next section)

.. code-block:: bash

    $ zmon-slr report create myproduct


Command Line Interface
======================

You can interact with API service using CLI tool ``zmon-slr``.

Examples:


.. code-block:: bash

    $ python setup.py install

    $ zmon-slr -h

    Usage: zmon-slr [OPTIONS] COMMAND [ARGS]...

      Service Level Reporting command line interface

    Options:
      -h, --help  Show this message and exit.

    Commands:
      configure  Configure CLI
      group      SLR product groups
      product    SLR products
      sli        Service level indicators
      slo        Service level objectives
      target     Service level objectives Targets

    $ zmon-slr group create "Monitoring Inc." "Tech Infrastructure"
    Creating product_group: Monitoring Inc.
    {
      "created": "2017-06-19T12:31:44.665459Z",
      "department": "Tech Infrastructure",
      "updated": "2017-06-19T12:31:44.665473Z",
      "slug": "monitoring-inc",
      "name": "Monitoring Inc.",
      "uri": "http://localhost:8080/api/product-groups/1",
      "username": "username"
    }
     OK

    $ zmon-slr group list
    [
      {
        "created": "2017-06-19T12:31:44.665459Z",
        "department": "Tech Infrastructure",
        "updated": "2017-06-19T12:31:44.665473Z",
        "slug": "monitoring-inc",
        "name": "Monitoring Inc.",
        "uri": "http://localhost:8080/api/product-groups/1",
        "username": "username"
      }
    ]

    $ zmon-slr product create ZMON monitoring-inc
    Creating product: ZMON
    {
      "product_reports_uri": "http://localhost:8080/api/products/1/reports",
      "product_reports_weekly_uri": "http://localhost:8080/api/products/1/reports/weekly",
      "username": "username",
      "slug": "zmon",
      "product_slo_uri": "http://localhost:8080/api/products/1/slo",
      "updated": "2017-06-19T12:34:51.818225Z",
      "product_group_uri": "http://localhost:8080/api/product-groups/1",
      "product_group_name": "Monitoring Inc.",
      "name": "ZMON",
      "product_sli_uri": "http://localhost:8080/api/products/1/sli",
      "uri": "http://localhost:8080/api/products/1",
      "created": "2017-06-19T12:34:51.818210Z"
    }
     OK

    $ zmon-slr product delete zmon
    Deleting product: zmon
     OK

    $ zmon-slr group delete monitoring-inc
    Deleting product_group: monitoring-inc
     OK
