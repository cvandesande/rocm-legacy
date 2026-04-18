#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y \
  wget \
  gpg \
  ca-certificates \
  software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y \
  python3.11 \
  python3.11-dev \
  python3.11-venv \
  python3.11-distutils

wget -q https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
python3.11 /tmp/get-pip.py
rm -f /tmp/get-pip.py

ln -sf /usr/bin/python3.11 /usr/bin/python3
printf '#!/bin/sh\nexec /usr/bin/python3.11 -m pip "$@"\n' > /usr/local/bin/pip3
chmod +x /usr/local/bin/pip3

rm -rf /var/lib/apt/lists/*
