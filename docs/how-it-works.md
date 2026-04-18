# How it works

This project separates compatibility concerns from application concerns.

## Layers

1. A pinned ROCm-era runtime and toolchain that still knows about the target GPU family
2. An ONNX Runtime build compiled for a specific HIP architecture
3. An application image that consumes the built wheel
4. A profile file that ties the pieces together

## Why profiles exist

Older GPUs often need a known-good combination of:

- ROCm version
- ONNX Runtime version
- HIP architecture target
- HSA override value
- optional environment toggles

A profile makes that combination explicit and reviewable.
