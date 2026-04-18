# rocm-legacy

Frigate image builds for legacy AMD GPUs using pinned ROCm-era userspace and ONNX Runtime ROCm wheels.

## What this is

`rocm-legacy` is a practical build repo for reviving older AMD GPUs that are no longer supported in current ROCm releases, but can still be useful for inference workloads.

The primary output of this repository is a Frigate-compatible container image. A secondary validation target is included to help check whether ONNX Runtime still exposes ROCm support before deploying the full application.

## Primary use case

The intended workflow is:

1. pick a compatibility profile
2. build a Frigate image
3. push that image to a registry such as GHCR
4. deploy it to a Kubernetes node with AMD GPU access

## Repository structure

- `profiles/` contains tested and experimental GPU family profiles
- `docker/Dockerfile` contains the shared multi-target build
- `docker/scripts/` contains the reusable setup and build logic used by the Docker targets
- `k8s/` contains example Kubernetes manifests for deploying the image
- `scripts/` contains convenience helpers for validation
- `docs/` contains the support matrix and project notes

## Build a Frigate image

1. Copy a profile into `.env`:

```bash
cp profiles/gfx803.env .env
```

2. Set the GPU access group IDs from the host:

```bash
getent group video
getent group render
```

3. Update `.env` with the matching `VIDEO_GID` and `RENDER_GID` values.

4. Build the Frigate image:

```bash
docker compose build frigate
```

## Push the image to GHCR

Example:

```bash
docker tag rocm-legacy-frigate ghcr.io/cvandesande/frigate-rocm-legacy:gfx803

docker push ghcr.io/cvandesande/frigate-rocm-legacy:gfx803
```

Adjust the tag to match your profile and release process.

## Validation target

The `onnx-smoke` target is kept as a diagnostic tool. It is useful for verifying that the pinned userspace and ONNX Runtime wheel still build cleanly and that the runtime reports ROCm support on a real host.

```bash
docker compose build onnx-smoke
docker compose run --rm onnx-smoke
```

## Kubernetes deployment notes

The example manifests under `k8s/` are intentionally generic. They are meant as a starting point for clusters that already provide AMD GPU access on selected nodes.

In practice you will usually need to adapt at least:

- image name and tag
- Frigate config mount path and storage class
- node selectors and tolerations for GPU nodes
- device plugin expectations or host device exposure model
- ingress, service, and persistent storage choices

## CI validation scope

GitHub Actions in this repository validates that the Docker and Compose configuration remain buildable and internally consistent.

That CI does **not** prove:

- that ROCm can execute on a given host
- that a specific legacy GPU profile works at runtime
- that ONNX Runtime will successfully expose `ROCMExecutionProvider` on your machine
- that Frigate will sustain inference correctly under real workloads

In other words, CI passing means the project still builds. It does not replace local hardware validation.

## Notes

This project is intentionally conservative about what it claims. A profile being present does not mean it is broadly supported by AMD, ROCm, or an upstream application vendor. It only means the profile is structured for testing here.

## Initial profiles

- `gfx803`: tested pattern for Polaris / RX 500 style cards
- `gfx906`: placeholder profile for future validation

## License

MIT
