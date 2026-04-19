# rocm-legacy

Frigate image builds for legacy AMD GPUs using pinned ROCm versions and ONNX Runtime ROCm wheels.

## What you get

This repository builds a Frigate image with:

- a pinned Frigate base image, defaulting to `ghcr.io/blakeblackshear/frigate:0.17.1`
- pinned ROCm userspace, defaulting to ROCm `5.5.1` for the `gfx803` profile
- a pinned ONNX Runtime ROCm wheel, defaulting to ONNX Runtime `v1.16.3`
- ONNX Runtime compiled for the GPU architecture selected by the active profile, such as `gfx803`

In other words, it builds a Frigate image with an old version of ROCM that supported older AMD GPUs.

## Tested defaults

| Component | Default / tested value |
|---|---|
| Frigate base image | `ghcr.io/blakeblackshear/frigate:0.17.1` |
| ONNX Runtime | `v1.16.3` |
| Primary tested profile | `gfx803` |
| ROCm for `gfx803` | `5.5.1` |
| HIP architecture for `gfx803` | `gfx803` |
| HSA override for `gfx803` | `8.0.3` |

## Profile matrix

| Profile | ROCm | ONNX Runtime | HIP arch | HSA override | Status |
|---|---:|---:|---|---|---|
| `gfx803` | `5.5.1` | `v1.16.3` | `gfx803` | `8.0.3` | tested pattern |
| `gfx906` | `5.7.3` | `v1.16.3` | `gfx906` | `9.0.6` | placeholder |

## What this is

`rocm-legacy` is a practical build repo for reviving older AMD GPUs that are no longer supported in current ROCm releases, but can still be useful for inference workloads.

The primary output of this repository is a Frigate-compatible container image.

## Usage

This repository is intentionally Docker- and Compose-focused.

The intended workflow is:

1. pick a compatibility profile
2. build a Frigate image
3. optionally run the image locally with Docker Compose
4. tag and push the image to your own registry

Kubernetes-specific deployment details are out of scope for this project.

## Repository structure

- `profiles/` contains tested and experimental GPU family profiles
- `docker/Dockerfile` contains the shared multi-target build
- `docker/scripts/` contains the reusable setup and build logic used by the Docker targets
- `scripts/` contains convenience helpers for validation
- `docs/` contains the support matrix and project notes

## Build a Frigate image

1. Copy a profile into `.env`:

```bash
cp profiles/gfx803.env .env
```

2. Build the Frigate image:

```bash
docker compose build frigate
```

The host GPU access group IDs are **not** needed for image builds. They only matter when you run the container with GPU device access on a specific host.

## Run locally with Docker Compose

If you want to run the container locally with Docker Compose, get the GPU access groups from the runtime host:

```bash
getent group video
getent group render
```

Then update `.env` with the matching `VIDEO_GID` and `RENDER_GID` values for that host.

Run locally:

```bash
docker compose up frigate
```

or for a one-shot test run:

```bash
docker compose run --rm frigate
```

## Validation target

The `onnx-smoke` target is kept as a diagnostic tool. It is useful for verifying that the pinned userspace and ONNX Runtime wheel still build cleanly and that the runtime reports ROCm support on a real host.

```bash
docker compose build onnx-smoke
docker compose run --rm onnx-smoke
```

## Build, tag, and push your own image

After `docker compose build frigate`, tag the built image for your own registry.

## CI validation scope

GitHub Actions in this repository validates that the Docker and Compose configuration remain buildable and internally consistent.

This project is intentionally conservative about what it claims. A profile being present does not mean it is broadly supported by AMD, ROCm, or an upstream application vendor. It only means the profile is structured for testing here.

## License

MIT
