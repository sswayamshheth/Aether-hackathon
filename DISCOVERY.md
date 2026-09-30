# DISCOVERY.md - repo discovery (Phase 1)

Checked 2026-09-30 through the GitHub API (`gh api`) and the Hugging Face API.
Stars, licence field, last commit and file trees below are read from those APIs,
not from the READMEs. Nothing has been cloned or run yet; "runs on this machine"
is decided in BENCH.md.

## The licence problem (read this first)

**None of the six suggested application repos has a licence file.** GitHub reports
`license: null` for all six. With no licence, the default is all rights reserved:
we may read the code, but copying code or shipping their weights is not covered.

Three of them claim MIT only in a README badge, with no LICENSE file to back it:

| Repo | What the README says | What the repo contains |
|---|---|---|
| BariaHarshh/CCTV-Surveillance-System | badge: "license-MIT" | no LICENSE file |
| CostiCatargiu/NewLuggageDataset | badge: "License-MIT"; dataset table: "License: MIT" | no LICENSE file |
| wanboyang/anomaly_detection_LAD2000 | badge: "License-MIT" linking to `LICENSE` | no LICENSE file (link is dead) |

How we handle it:
- Bench them all the same (running code locally to measure it is fine).
- From unlicensed repos we take **ideas and logic, re-implemented in our own code**,
  and credit the source in CREDITS.md. We do not copy their files.
- We ship **weights only when they are licensed** (Hugging Face MIT / Apache-2.0,
  Ultralytics AGPL-3.0) **or trained by us** on openly licensed data.
- If a README-badge "MIT" repo wins a task outright, we say "MIT per README badge,
  no licence file" in CREDITS.md rather than overstate it.

## Suggested candidates

| Repo | Licence (GitHub field) | Last commit | Stars | Weights in repo | Datasets | Windows / Py 3.13 | Code quality | Verdict |
|---|---|---|---|---|---|---|---|---|
| BariaHarshh/CCTV-Surveillance-System | none (README badge "MIT") | 2026-09-26 `e020fd0f78` | 0 | none; downloads COCO `yolov8n.pt` from Ultralytics | none (COCO pretrained only) | likely fine: loose `>=` pins, FastAPI + Ultralytics | best of the six: feature packages, YAML presets, 17 test files | **shortlist** (crowd, baggage, multi-cam) |
| srniloy/accident-detection | none | 2025-11-08 `3581885a4f` | 2 | yes: `Edge_Device/model/accident_detection.pt`, 5.3 MB, YOLO11n, classes `accident / moderate / severe` | Roboflow `ann-qwhjm/accident-detection-cwbvs` v2, "license: CC BY 4.0" (from `data1.yaml`) | fine: two short Python files | thin: single-image inference script, MQTT publisher | **shortlist** (accident + severity, CPU-sized) |
| saudrawdhan/Yaqiz-Emergency-Response | none | 2026-09-08 `46dfad9d48` | 0 | none | CADP (notebook names) | n/a | notebooks plus a React GUI tied to Supabase; no inference code, no weights | drop |
| kircova/Car-Crash-Detection | none at root (a LICENSE sits inside `accident_detection/`) | 2023-07-14 `979438d2b7` | 23 | none (`weights/` is an empty placeholder) | not stated | risky: YOLOv3 Darknet port, Python 3.9 bytecode committed | one notebook, centroid tracker | drop (idea only: trajectory-based crash scoring) |
| CostiCatargiu/NewLuggageDataset | none (README: dataset "License: MIT") | 2026-09-20 `7f894fb063` | 2 | none in repo (results on Google Drive) | own luggage set, 29,053 images, classes backpack / bag / trolley, on Roboflow Universe | n/a | 5,086 files of training runs and thesis drafts, also unrelated tooling; no clean inference entry point found | not runnable as a repo; **keep the dataset** as the M3 fine-tune source |
| wanboyang/anomaly_detection_LAD2000 | none (README badge "MIT", dead link) | 2025-10-22 `ca51f97361` | 35 | none (repo is 94 KB) | LAD2000, UCSD Ped2, Avenue, ShanghaiTech, UCF-Crime | poor fit: conda env, needs pre-extracted I3D features | clean research code | drop: I3D feature extraction is not real time on this CPU |

## Extra candidates found

| Repo / model | Licence | Last update | Stars / downloads | What it gives | Verdict |
|---|---|---|---|---|---|
| Enos-123/traffic-accident-detection-yolo11x (Hugging Face) | **MIT** (model card) | 2025-06-25 | 222 downloads | YOLO11x accident detector, 114 MB, trained on Roboflow `hilmantm/traffic-accident-detection` | **shortlist**: licensed accident weights. x-size, so expect it to be slow on CPU |
| dri11heaD/rtdetr-accident-cctv (Hugging Face) | **Apache-2.0** | 2026-08-18 | 11 downloads | RT-DETR r18, 80 MB, classes Accident / Non-accident; card does not name the dataset | reserve if the YOLO11x is too slow |
| hilmantm/detr-traffic-accident-detection (Hugging Face) | Apache-2.0 | 2025-04-12 | 315 downloads | DETR-ResNet50, 166 MB, accident + vehicle | reserve |
| neyvur/traffic-video-analysis | none | 2026-09-27 `ef874a667c` | 0 | rule-and-trajectory traffic events (accident, near miss, stopped vehicle...) on COCO YOLOv8n, zone annotation tool, CPU torch index in requirements | **shortlist**: tracking-based accident logic, the explainable fallback |
| saadkhan2003/CCTV_Video_Anomaly_Detection | **Apache-2.0** (LICENSE file; README badge says MIT) | 2026-08-09 `4ab4eb0349` | 4 | YOLO11s exported to OpenVINO (in repo), ByteTrack, crowd / loitering / fast-movement rules, sample clips | **shortlist**: crowd anomalies on Intel CPU, the closest match to our hardware |
| TheRomanFour/AbandonedLuggageDetection | none | 2026-07-20 `499eb4839c` | 6 | custom YOLOv8s person + suitcase weights (`korzo_model.pt`, 22 MB), owner-link and radius logic, test clips (AI-generated) | **shortlist**: only baggage repo with trained weights in the repo |
| Kevinjoythomas/Unattended-Baggage-Detection | **Apache-2.0** | 2024-10-17 `91e1ac8c06` | 4 | two files: COCO YOLOv8s + DeepSORT, bag-to-owner distance and time rule | reserve: clean licence, small |
| kirishipathi/AI_CROWD__ | **MIT** (LICENSE file) | 2026-06-20 `4fcbaa3c5c` | 15 | YOLOv8 + SORT, density, movement and cluster analysis modules | reserve for crowd features |
| AmineSam/irail-crowd-counting-yolov8n (Hugging Face) | CC BY-SA 4.0 (share-alike) | 2026-01-20 | 206 downloads | YOLOv8n head detector, 6.3 MB, for dense crowds where full bodies are hidden | reserve: useful for dense-crowd counting and head blurring |
| Amey-Thakur/ACCIDENT-CVPR-2026 | CC-BY-4.0 | 2026-09-06 | 4 | one notebook, zero-shot CLIP pipeline | drop: notebook only |
| dolongbien/HumanBehaviorBKU | none | 2022-12-08 | 169 | C3D road-accident anomaly model | drop: Keras 1.1 / Theano / Caffe |
| YoussefKabbary/Crowd-Intelligence-System | custom, README: "all rights reserved" | 2026-09-26 | 6 | crowd analytics, single 208 KB file | drop: licence forbids reuse |

## Infrastructure (all confirmed)

| Library | Licence | Latest release | Pin | Use |
|---|---|---|---|---|
| ultralytics/ultralytics | AGPL-3.0 | v8.4.168 (2026-09-30) | 8.4.168 | detection, built-in ByteTrack, ONNX / OpenVINO export |
| roboflow/supervision | MIT | 0.30.6 (2026-09-29) | 0.30.6 | zones, annotators, line and polygon tools |
| mikel-brostrom/boxmot | AGPL-3.0 | v25.0.0 (2026-09-09) | 25.0.0 | only if we add OSNet re-ID (nice-to-have) |
| bluenviron/mediamtx | MIT | v1.21.1 (2026-09-20) | v1.21.1 | RTSP server; Windows zip is 26 MB |

All four publish Python 3.13-compatible builds (PyPI `requires_python` checked).
AGPL-3.0 note: using Ultralytics means our project must be released under
AGPL-3.0-compatible terms. Fine for a hackathon repo; it goes in the README.

## Ranked shortlist (6)

| # | Repo | Task | Pinned commit | Why it made the list | Main risk |
|---|---|---|---|---|---|
| 1 | srniloy/accident-detection | accident | `3581885a4f` | only accident model with severity classes that is nano-sized; dataset is CC BY 4.0 so we can retrain the same thing ourselves | repo has no licence; trained on still images |
| 2 | Enos-123/traffic-accident-detection-yolo11x | accident | HF `cdc556d278` | MIT weights we can ship as-is | 114 MB x-model on a laptop CPU |
| 3 | neyvur/traffic-video-analysis | accident (rules) | `ef874a667c` | trajectory logic gives onset time and reasons, works on COCO classes | no licence; re-implement, do not copy |
| 4 | BariaHarshh/CCTV-Surveillance-System | crowd, baggage, multi-camera | `e020fd0f78` | covers the most of PS 06 in one codebase, has tests | no licence file; Next.js + MongoDB Atlas portal we do not want |
| 5 | saadkhan2003/CCTV_Video_Anomaly_Detection | crowd | `4ab4eb0349` | Apache-2.0, OpenVINO model already exported, built for CPU | heavy requirements list (pandas, plotly, jupyter...) |
| 6 | TheRomanFour/AbandonedLuggageDetection | baggage | `499eb4839c` | trained suitcase weights plus ownership logic in the repo | no licence; thesis-style scripts |

Coverage: accident 3, crowd 2, baggage 2. Reserves if something is BROKEN:
dri11heaD RT-DETR (accident), kirishipathi/AI_CROWD__ (crowd),
Kevinjoythomas/Unattended-Baggage-Detection (baggage).

## Install-script review

Read before running anything. Findings:

- **BariaHarshh/CCTV-Surveillance-System**: `start_system.py` runs `npm install`
  and `npx` with `shell=True` inside `web/`, and the portal expects MongoDB Atlas.
  We will **not** run `start_system.py` or the web portal, only the Python feature
  runners. The repo also commits a binary wheel,
  `scratch_ort/onnxruntime-1.30.0-cp314-cp314-win_amd64.whl` (14 MB, Python 3.14).
  Not referenced by `requirements.txt`; we will not install it. Outbound calls go to
  `localhost:3000` only. `download_models.py` fetches `yolov8n.pt` from the
  official Ultralytics release URL.
- **srniloy/accident-detection**: two short scripts; MQTT publishes to `localhost`.
  We load only the `.pt` file. Note that `.pt` files are pickles and can run code
  on load: loaded through Ultralytics in the repo's own venv, never in ours until
  re-exported to ONNX.
- **neyvur/traffic-video-analysis**: requirements add the official PyTorch CPU
  index (`download.pytorch.org/whl/cpu`). Nothing unusual.
- **saadkhan2003/CCTV_Video_Anomaly_Detection**: large but ordinary dependency
  list; has an email-alert module we will leave unconfigured.
- **TheRomanFour/AbandonedLuggageDetection**: plain scripts, no installer. Same
  pickle caution for `korzo_model.pt`.
- **CostiCatargiu/NewLuggageDataset**: contains unrelated tooling
  (`AI_DupeHunter_bench`, `.bat` build scripts, PyInstaller specs). Nothing from
  this repo gets executed; we only use the public dataset.
- No obfuscated code, credential harvesting or unexpected remote hosts seen in
  the files read. This was a read of launchers, requirements and entry points,
  not a line-by-line audit of every file.
