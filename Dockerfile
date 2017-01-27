FROM registry.opensource.zalan.do/stups/python:latest

# libpq-dev is needed for PostgreSQL driver
RUN apt-get update && apt-get install -y libpq-dev

COPY requirements.txt /
RUN pip3 install -r /requirements.txt

COPY app /app

# http://docs.stups.io/en/latest/user-guide/application-development.html#scm-source-json
COPY scm-source.json /

CMD python -m app.main
