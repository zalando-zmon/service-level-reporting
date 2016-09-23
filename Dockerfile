FROM registry.opensource.zalan.do/stups/python:3.5.2-37

# libpq-dev is needed for PostgreSQL driver
RUN apt-get update && apt-get install -y libpq-dev

COPY requirements.txt /
RUN pip3 install -r /requirements.txt

COPY slo.py /
COPY app.py /
COPY swagger.yaml /

# http://docs.stups.io/en/latest/user-guide/application-development.html#scm-source-json
COPY scm-source.json /

CMD /app.py
