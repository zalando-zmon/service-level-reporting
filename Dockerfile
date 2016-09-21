FROM registry.opensource.zalan.do/stups/python:3.5.1-33

RUN apt-get update && apt-get install -y libpq-dev

COPY requirements.txt /
RUN pip3 install -r /requirements.txt

COPY slo.py /
COPY app.py /
COPY swagger.yaml /

CMD /app.py
