# Free YOLOv9 model guide

This guide creates a freely available YOLOv9-t model (640×640 by default, set
`IMGSZ` for another size) for the ncnn
Vulkan detector. It deliberately uses the public Ultralytics model download
and does not depend on any entitlement-specific model source.

"Freely available" here means obtainable without an entitlement, not
unencumbered -- see "Model licensing" below before publishing anything derived
from one.

## Export the model

From the repository root, run:

```bash
scripts/export_ncnn_model.sh
```

The script runs a pinned Ultralytics container and downloads the public
`yolov9t.pt` model on its first run. It exports both ncnn and ONNX artifacts at
640×640 by default, then writes these files under `models/`:

```text
yolov9t-640.ncnn.param
yolov9t-640.ncnn.bin
yolov9t-640.onnx
yolov9t-640.ncnn.metadata.yaml   # when supplied by the exporter
yolov9t-640-labelmap.txt         # derived from metadata.yaml
```

Set `IMGSZ` to export a different input resolution (any multiple of 32):

```bash
IMGSZ=320 scripts/export_ncnn_model.sh
```

That produces `yolov9t-320.*` instead. Because the size is in the filename,
resolutions do not overwrite each other. Keep the Frigate `model:` block's
`width` and `height` in step with whichever you deploy.

The labelmap is generated from the exporter's own `metadata.yaml` `names`
mapping, so the class order always matches the model. Do not transcribe class
names by hand: `metadata.yaml` stores them as YAML (`0: person`), but Frigate
requires space-delimited lines (`0 person`), and a colon-delimited labelmap is
accepted without error while mislabelling every class. See the labelmap format
section in the README.

It also prints SHA-256 checksums. Record the checksums when testing or
deploying a model so that the exact model can be reproduced later.

The model directory is gitignored: do not commit generated weights or use a
public image registry to distribute them without reviewing the model's license.

## Model licensing

**Read this before publishing anything containing an exported model.**

`yolov9t.pt` is downloaded from Ultralytics, whose code and published weights are
**AGPL-3.0**, or a paid Enterprise licence. The `.param` and `.bin` this script
produces are derived from those weights, so they inherit that. Upstream YOLOv9
(WongKinYiu) is GPL-3.0, so avoiding Ultralytics is not the same as avoiding
copyleft.

**This repository ships the exporter, not the model, and that distinction is the
point.** A script that names a pinned upstream image is our own work; running it
is what fetches AGPL material, and it lands on the machine that ran it under
whatever terms Ultralytics offers directly. Nothing here redistributes a model:
`models/` is gitignored, no published image contains weights, and CI only
syntax-checks this script rather than running it.

Where the obligation actually attaches, for anyone using it:

- **Running a model privately** -- on your own cameras, for yourself -- triggers
  nothing. This is the normal case.
- **Publishing exported weights**, or an image with them baked in, conveys AGPL
  material and pulls in the corresponding-source requirement.
- **Offering it as a network service** is what AGPL §13 exists for, and is the
  case worth thinking about hardest if this ever becomes a product rather than a
  deployment.

If a permissively licensed detector matters more than YOLOv9 specifically,
Apache-2.0 models exist (YOLOX, NanoDet, RT-DETR variants). That is a real port
rather than a config change: the ncnn plugin's post-processing assumes the
YOLO-generic output contract, so a different output layout needs
`post_process_yolo` replaced.

None of this is legal advice; it is a reading of the upstream licences, and the
question of whether trained weights are a derivative work of the training code is
genuinely unsettled. Ultralytics' own stated position is the assertive one.

## Validate it on the GPU

Set the target host's video and render group IDs in `.env`, then run:

```bash
docker compose run --rm vulkan-smoke
```

The default smoke paths already use `/models/yolov9t-640.ncnn.param` and its
matching `.bin` file. If you exported a different `IMGSZ`, point `MODEL_PARAM`
at that file instead (for example `/models/yolov9t-320.ncnn.param`). The test requires a Vulkan GPU, checks that ncnn sees the
GPU, measures inference, and compares Vulkan output with CPU output. With the
default `NCNN_FP16=0`, it fails when the maximum CPU/GPU difference is
`>= 1e-2`.

## Use it with Frigate

Mount `models/` into the Frigate container and set the model path to the
exported `.ncnn.param`; its matching `.ncnn.bin` must be in the same directory.
Use the model metadata to supply the matching class labels in the Frigate model
configuration. The exact label-map setting depends on the Frigate version and
configuration already in use, so retain the exporter-generated metadata rather
than substituting labels from a different model.

The ncnn plugin supports raw-YOLO-compatible models. Do not assume that an
arbitrary ONNX model will work: its input layout, data type, output layout, and
post-processing must match the detector configuration. Validate every new
export with `vulkan-smoke` before using it for live detections.

## Other public YOLOv9 variants

To export another public YOLOv9 variant or resolution, adapt the `yolo export`
commands in `scripts/export_ncnn_model.sh`, keep the model's `.param` and
`.bin` together, and update the width and height in the Frigate configuration.
Run the smoke test again: larger models and resolutions can materially change
latency on gfx803 hardware.
