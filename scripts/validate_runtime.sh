#!/usr/bin/env bash
set -euo pipefail

python3 <<'PY'
import os
import onnxruntime as ort
print('PROFILE_NAME=', os.getenv('PROFILE_NAME', 'unknown'))
print('HSA_OVERRIDE_GFX_VERSION=', os.getenv('HSA_OVERRIDE_GFX_VERSION', 'unset'))
print('ROC_ENABLE_PRE_VEGA=', os.getenv('ROC_ENABLE_PRE_VEGA', 'unset'))
print('ORT=', ort.__version__)
print('PROVIDERS=', ort.get_available_providers())
PY
