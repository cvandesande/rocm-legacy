#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <repo_deb_url> [usecase]" >&2
  exit 1
fi

REPO_DEB_URL="$1"
USECASE="${2:-lrt,hip,mllib}"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y wget gpg ca-certificates software-properties-common libnuma1
wget -O /tmp/vendor-gpu-userspace.deb "${REPO_DEB_URL}"
apt-get update
apt-get install -y /tmp/vendor-gpu-userspace.deb
amdgpu-install -y --usecase="${USECASE}" --no-dkms
apt-get install -y migraphx half roctracer
rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/vendor-gpu-userspace.deb
