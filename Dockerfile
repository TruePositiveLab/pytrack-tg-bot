# vim: set ft=Dockerfile :
FROM gliderlabs/alpine
MAINTAINER Vladislav Bortnikov bortnikov.vladislav@e-sakha.ru

ADD image build
ADD requirements.txt build/requirements.txt

RUN /build/install_packages.sh && /build/cleanup.sh

WORKDIR /app

ADD *.py /app/
ADD db /app/db

VOLUME /app-data

ENTRYPOINT ["/sbin/tini", "--"]
CMD python3 main.py
