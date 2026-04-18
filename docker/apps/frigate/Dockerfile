# syntax=docker/dockerfile:1.7
ARG FRIGATE_IMAGE=ghcr.io/blakeblackshear/frigate:stable
ARG AMDGPU_DEB_URL
ARG ORT_TAG=v1.16.3
ARG HIP_ARCH=gfx803

FROM ubuntu:22.04 AS ort-builder
ARG DEBIAN_FRONTEND=noninteractive
ARG AMDGPU_DEB_URL
ARG ORT_TAG
ARG HIP_ARCH

RUN apt-get update && apt-get install -y \
    wget gpg ca-certificates git software-properties-common \
    build-essential ninja-build pkg-config libnuma-dev \
    patchelf zip unzip \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3.11-venv python3.11-distutils \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py \
    && python3.11 /tmp/get-pip.py \
    && rm -f /tmp/get-pip.py

RUN ln -sf /usr/bin/python3.11 /usr/bin/python3
RUN python3.11 -m pip install --upgrade pip setuptools wheel packaging "numpy<2" sympy "cmake>=3.27,<3.28"

RUN wget -O /tmp/amdgpu-install.deb "${AMDGPU_DEB_URL}" \
    && apt-get update \
    && apt-get install -y /tmp/amdgpu-install.deb \
    && amdgpu-install -y --usecase=rocmdev,hiplibsdk,mllib --no-dkms \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/amdgpu-install.deb

WORKDIR /src
RUN git clone --branch "${ORT_TAG}" --depth 1 https://github.com/microsoft/onnxruntime.git
WORKDIR /src/onnxruntime
RUN sed -i 's/be8be39fdbc6e60e94fa7870b280707069b5b81a/32b145f525a8308d7ab1c09388b2e288312d8eba/g' cmake/deps.txt || true
RUN ./build.sh \
    --config Release \
    --build_wheel \
    --parallel \
    --use_rocm \
    --rocm_home /opt/rocm \
    --skip_tests \
    --allow_running_as_root \
    --cmake_extra_defines \
      CMAKE_HIP_ARCHITECTURES=${HIP_ARCH}

FROM ${FRIGATE_IMAGE}
USER root
RUN apt-get update && apt-get install -y libnuma1 libstdc++-11-dev wget gpg ca-certificates software-properties-common && apt-get clean

ARG AMDGPU_DEB_URL
RUN wget -O /tmp/amdgpu-install.deb "${AMDGPU_DEB_URL}" \
    && apt-get update \
    && apt-get install -y /tmp/amdgpu-install.deb \
    && amdgpu-install -y --usecase=lrt,hip,mllib --no-dkms \
    && apt-get install -y migraphx half roctracer miopen-hip-dev \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/amdgpu-install.deb

COPY --from=ort-builder /src/onnxruntime/build/Linux/Release/dist/*.whl /tmp/
RUN python3 -m pip uninstall -y --break-system-packages onnxruntime onnxruntime-rocm || true \
    && python3 -m pip install --no-cache-dir --break-system-packages "numpy<2" \
    && python3 -m pip install --no-cache-dir --break-system-packages /tmp/*.whl \
    && rm -f /tmp/*.whl

ENV PATH=/opt/rocm/bin:/opt/rocm/hip/bin:/opt/rocm/llvm/bin:${PATH}
ENV ROCM_PATH=/opt/rocm
ENV ROCM_HOME=/opt/rocm
ENV HIP_PATH=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64

RUN python3 - <<'PY'
import onnxruntime as ort
print('ORT:', ort.__version__)
print('Providers:', ort.get_available_providers())
PY
