#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <ort_tag> <hip_arch>" >&2
  exit 1
fi

ORT_TAG="$1"
HIP_ARCH="$2"

python3.11 -m pip install --upgrade \
  pip setuptools wheel packaging "numpy<2" sympy "cmake>=3.27,<3.28"

mkdir -p /src
cd /src
if [[ ! -d /src/onnxruntime ]]; then
  git clone --branch "${ORT_TAG}" --depth 1 https://github.com/microsoft/onnxruntime.git
fi

cd /src/onnxruntime
sed -i 's/be8be39fdbc6e60e94fa7870b280707069b5b81a/32b145f525a8308d7ab1c09388b2e288312d8eba/g' cmake/deps.txt || true

./build.sh \
  --config Release \
  --build_wheel \
  --parallel \
  --use_rocm \
  --rocm_home /opt/rocm \
  --skip_tests \
  --allow_running_as_root \
  --cmake_extra_defines \
    CMAKE_HIP_ARCHITECTURES=${HIP_ARCH}
