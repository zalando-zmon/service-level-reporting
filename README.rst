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
    $ python -m app.main

Configuration parameters:

``OAUTH2_ACCESS_TOKENS_URL``
    Token endpoint URL.
``CREDENTIALS_DIR``
    Folder with OAuth application credentials (``client.json`` and ``user.json``).
``DATABASE_URI``
    PostgreSQL database connection string.
``KAIROSDB_URL``
    KairosDB base URL.

Generating Reports
==================

You will need to install ``gnuplot`` as a system dependency. Running the following command will generate a report for the specified project in ``output`` directory.

.. code-block:: bash

    $ ./generate-slr.py http://localhost:8080 myproduct


Command Line Interface
======================

You can interact with API service using CLI tool ``cli.py``.

Examples:


.. code-block:: bash

    $ pip3 install --update -r requirements.txt

    $ ./cli.py -h
    Usage: cli.py [OPTIONS] COMMAND [ARGS]...

      Service Level Reporting command line interface

    Options:
      -h, --help  Show this message and exit.

    Commands:
      configure    Configure CLI
      data-source  Data sources
      group        SLR product groups
      product      SLR products
      sli          Service level indicators
      slo          Service level objectives

    $ ./cli.py group create "Monitoring Inc." "Tech Infrastructure"
    Creating product_group: Monitoring Inc.
     OK

    $ ./cli.py group list
    [
        {
            "name": "Monitoring Inc.",
            "department": "Tech Infrastructure",
            "slug": "monitoring-inc"
        }
    ]

    $ ./cli.py product create ZMON monitoring-inc
    Creating product: ZMON
     OK

    $ ./cli.py product list
    [
        {
            "delivery_team": null,
            "department": "Tech Infrastructure",
            "product_group_id": 1,
            "slug": "zmon",
            "product_group_name": "Monitoring Inc.",
            "id": 2,
            "product_group_slug": "monitoring-inc",
            "name": "ZMON"
        }
    ]

    $ ./cli.py product delete zmon
    Deleting product: zmon
     OK

    $ ./cli.py group delete monitoring-inc
    Deleting product_group: monitoring-inc
     OK
