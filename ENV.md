# ENV.md - machine check (Phase 0)

Measured 2026-09-30 with PowerShell (`Get-CimInstance`, `Get-Command`, `--version`).

| Item | Value |
|---|---|
| OS | Windows 11 Home Single Language 10.0.26200 (build 26200) |
| CPU | 12th Gen Intel Core i5-1230U, 10 cores / 12 threads (low-power U series) |
| RAM | 15.7 GB total |
| GPU | Intel Iris Xe (integrated). No NVIDIA GPU, `nvidia-smi` not present, no CUDA |
| VRAM | none dedicated (shared system memory) |
| Free space E: | 88.8 GB |
| Free space C: | 4.7 GB (tight) |
| Python | 3.13.5 (only version installed, `py -0p` shows 3.13 only) |
| Node | v24.18.0, npm 11.16.0 |
| git | 2.51.1.windows.1 |
| GitHub CLI | installed |
| Chrome | 154.0.8037.58 |
| ffmpeg / ffprobe | NOT installed |
| MediaMTX | NOT installed |
| Kaggle CLI | NOT installed; `%USERPROFILE%\.kaggle\kaggle.json` does not exist |

## Decisions

- **Inference: CPU.** There is no CUDA GPU. Plan: Ultralytics YOLO nano, exported to
  ONNX or OpenVINO (Iris Xe / CPU), detect every 2-3 frames, 4 cameras at reduced
  resolution. Real FPS will be measured in BENCH.md, not assumed.
- **Training: Kaggle GPU only.** Nothing is trained locally. No Kaggle token is
  present, so notebooks will be handed over with manual run steps unless a token
  is added.
- **Package caches go on E:, not C:.** C: has 4.7 GB free and pip's default cache
  is `C:\Users\ssway\AppData\Local\pip\cache`. One torch install could fill it.
  All pip/npm commands for this project set `PIP_CACHE_DIR` and `npm_config_cache`
  to `E:\sss\study\btech\aether-hackathon\.cache\`.
- **Python 3.13 only.** Older reference repos that pin old torch / numpy may not
  install on 3.13. That counts against them in the bench (30-minute limit each).
- **ffmpeg and MediaMTX: portable builds inside the project** (`tools\`), not
  system installs. Needed for the bench clips (ffmpeg) and RTSP simulation (both).

## Blocking risks found

1. **Memory is almost exhausted right now.** At check time: 0.8 GB RAM free,
   commit charge 27.1 GB of 28.4 GB. Biggest holders: python 6.6 GB across 11
   processes (the running trading apps), Chrome 4.3 GB across 27 processes,
   Claude 2.6 GB, WebView2 1.7 GB. This machine crashed from exactly this state
   on 2026-09-28. Installing torch and running YOLO needs roughly 3-4 GB of
   headroom, so Phase 1B cannot start safely until memory is freed.
2. **C: is nearly full** (4.7 GB). Handled by moving caches to E: (above).
3. **No GPU.** 4 live streams plus an uploaded video on a 15 W U-series CPU is
   the main performance risk for the demo. Demo mode (cached detections) is the
   safety net.
