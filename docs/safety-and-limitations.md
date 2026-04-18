# Safety and limitations

This project uses older ROCm-era components to keep unsupported GPUs useful for experimentation and light inference workloads.

## Limitations

- Upstream vendors may no longer support the GPU or software stack
- Security fixes for older components may lag or never arrive
- Some models will not fit in limited VRAM
- Some workloads may silently fall back to CPU if the runtime is misconfigured
- Host kernel and driver combinations still matter even when containers are used

## Scope

This repository is for experimentation, learning, and practical reuse of older hardware. It should not be treated as vendor-supported production infrastructure without substantial validation.
