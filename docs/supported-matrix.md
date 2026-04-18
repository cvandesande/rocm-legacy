# Supported matrix

| Profile | Example family | ROCm | ORT | App target | Status |
|---|---|---:|---:|---|---|
| gfx803 | Polaris / RX 500 style cards | 5.5.1 | v1.16.3 | Frigate + ONNX | tested pattern |
| gfx906 | Vega 20 / MI50 class | 5.7.3 | v1.16.3 | ONNX smoke test | placeholder |

## Support levels

- Level 1: Image builds successfully
- Level 2: ONNX Runtime exposes `ROCMExecutionProvider`
- Level 3: Minimal inference works
- Level 4: App integration works under sustained use
