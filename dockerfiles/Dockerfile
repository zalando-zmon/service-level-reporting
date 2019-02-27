FROM registry.opensource.zalan.do/stups/python:latest

# libpq-dev is needed for PostgreSQL driver
RUN apt-get update && apt-get install -y libpq-dev dnsutils libdpkg-perl python3-dev

COPY requirements.txt /
RUN pip3 install -r /requirements.txt

RUN pip3 install -U sqlalchemy-utils

COPY dockerfiles/migrate.py /migrate.py

RUN chmod a+x /migrate.py

COPY app /app

COPY swagger.yaml /

ENV FLASK_APP /app/main.py

CMD python -m app
