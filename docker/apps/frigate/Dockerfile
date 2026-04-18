# syntax=docker/dockerfile:1.7
ARG FRIGATE_IMAGE=ghcr.io/blakeblackshear/frigate:stable
ARG AMDGPU_DEB_URL
ARG ORT_TAG=v1.16.3
ARG HIP_ARCH=gfx803

FROM ubuntu:22.04 AS ort-builder
ARG AMDGPU_DEB_URL
ARG ORT_TAG
ARG HIP_ARCH
ENV ROCM_PATH=/opt/rocm
ENV ROCM_HOME=/opt/rocm
ENV HIP_PATH=/opt/rocm
ENV PATH=/opt/rocm/bin:/opt/rocm/hip/bin:/usr/local/bin:${PATH}
COPY docker/scripts/install_python311.sh /usr/local/bin/install_python311.sh
COPY docker/scripts/setup_rocm_userspace.sh /usr/local/bin/setup_rocm_userspace.sh
COPY docker/scripts/build_ort_wheel.sh /usr/local/bin/build_ort_wheel.sh
RUN chmod +x /usr/local/bin/install_python311.sh /usr/local/bin/setup_rocm_userspace.sh /usr/local/bin/build_ort_wheel.sh \
    && apt-get update \
    && apt-get install -y git build-essential ninja-build pkg-config libnuma-dev patchelf zip unzip \
    && /usr/local/bin/install_python311.sh \
    && /usr/local/bin/setup_rocm_userspace.sh "${AMDGPU_DEB_URL}" rocmdev,hiplibsdk,mllib \
    && /usr/local/bin/build_ort_wheel.sh "${ORT_TAG}" "${HIP_ARCH}"

FROM ${FRIGATE_IMAGE}
USER root
ARG AMDGPU_DEB_URL
ENV PATH=/opt/rocm/bin:/opt/rocm/hip/bin:/opt/rocm/llvm/bin:${PATH}
ENV ROCM_PATH=/opt/rocm
ENV ROCM_HOME=/opt/rocm
ENV HIP_PATH=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64
COPY docker/scripts/setup_rocm_userspace.sh /usr/local/bin/setup_rocm_userspace.sh
RUN chmod +x /usr/local/bin/setup_rocm_userspace.sh \
    && apt-get update \
    && apt-get install -y libstdc++-11-dev \
    && /usr/local/bin/setup_rocm_userspace.sh "${AMDGPU_DEB_URL}" lrt,hip,mllib
COPY --from=ort-builder /src/onnxruntime/build/Linux/Release/dist/*.whl /tmp/
RUN python3 -m pip uninstall -y --break-system-packages onnxruntime onnxruntime-rocm || true \
    && python3 -m pip install --no-cache-dir --break-system-packages "numpy<2" \
    && python3 -m pip install --no-cache-dir --break-system-packages /tmp/*.whl \
    && rm -f /tmp/*.whl
RUN python3 - <<'PY'
import onnxruntime as ort
print('ORT:', ort.__version__)
print('Providers:', ort.get_available_providers())
PY
