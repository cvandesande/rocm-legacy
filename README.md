# rocm-legacy

Containerized compatibility environment for legacy AMD GPUs using pinned ROCm-era toolchains and app-specific runtime builds.

## What this is

`rocm-legacy` is a starter framework for reviving older AMD GPUs that are no longer supported in current ROCm releases, but can still run useful AI inference workloads when paired with older pinned toolchains and carefully built runtime images.

The first target is ONNX Runtime with ROCm, with Frigate as a flagship application example.

## Goals

- Reduce e-waste by extending the useful life of older GPUs
- Provide a repeatable build structure instead of one-off Dockerfiles
- Make compatibility profiles explicit and documented
- Separate the compatibility layer from the application layer

## Current structure

- `profiles/` contains tested and experimental GPU family profiles
- `docker/base/` contains reusable ROCm runtime and ONNX Runtime builder stages
- `docker/apps/` contains application-specific images such as Frigate and minimal ONNX Runtime smoke tests
- `scripts/` contains convenience helpers for detection and validation
- `docs/` contains the support matrix and project notes

## Quick start

1. Copy a profile into `.env`:

```bash
cp profiles/gfx803.env .env
```

2. Build the minimal smoke-test image:

```bash
docker compose build onnx-smoke
```

3. Run the smoke test with GPU devices exposed:

```bash
docker compose run --rm onnx-smoke
```

4. Build the Frigate image once the smoke test works:

```bash
docker compose build frigate
```

## Notes

This project is intentionally conservative about what it claims. A profile being present does not mean it is broadly supported by AMD, ROCm, or an upstream application vendor. It only means the profile is structured for testing here.

## Initial profiles

- `gfx803`: tested pattern for Polaris / RX 500 family style cards
- `gfx906`: placeholder profile for future validation

## License

MIT
