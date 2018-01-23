#!/bin/sh
set -e
source /build/buildconfig
set -x

apk add --no-cache build-base \
    ca-certificates \
    gettext \
    jpeg-dev \
    libwebp-dev \
    libxml2-dev \
    python3-dev \
    zlib-dev \
    git \
    tini
# install python requirements
LIBRARY_PATH=/lib:/usr/lib \
pip3 install -U setuptools
pip3 install -U \
    --no-cache-dir \
    -r /build/requirements.txt
