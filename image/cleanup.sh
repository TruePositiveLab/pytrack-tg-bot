#!/bin/sh
set -e
source /build/buildconfig
set -x
rm -rf /build
rm -rf /app/image

apk del --no-cache build-base \
    git
