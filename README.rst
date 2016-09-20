====================
ZMON SRE SLO Metrics
====================

**WORK IN PROGRESS**

Calculate SLI/SLO metrics using ZMON's KairosDB timeseries database.

Idea:

* Retrieve metrics such as latencies and error counts from KairosDB
* Aggregate metrics, weighted by requests/s
* Push metrics truncated to full minute timestamps into PostgreSQL

.. code-block:: bash

    $ docker run -d -p 5432:5432 postgres:9.5
    $ cat schema.sql | psql -h localhost -U postgres
    $ cat sample_data.sql | psql -h localhost -U postgres
