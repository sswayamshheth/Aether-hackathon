# What we built, and what we took

For judge questions. Short version: the detector weights are pretrained and credited; the
pipeline around them, the nine incident engines, the crowd model, the ML verifiers, the
incident layer and the dashboard are ours. No source file from another project is copied
into this repo.

## Taken as-is (pretrained or off the shelf)

| Piece | From | How it is used |
|---|---|---|
| Object detector | Ultralytics YOLO11n, COCO weights (AGPL-3.0) | people, vehicles and bags on every camera, exported by us to OpenVINO |
| Tracker | ByteTrack as implemented in Ultralytics | one tracker instance per camera, for people and vehicles |
| Accident detector | `Enos-123/traffic-accident-detection-yolo11x` on Hugging Face (MIT) | run about once a second per camera by the model scheduler |
| Fire and smoke detector | `rabahdev/fire-smoke-yolov8n` (AGPL-3.0, D-Fire dataset) | once a second per camera |
| Weapon detector | `weapon_detector.pt` from saadkhan2003/CCTV_Video_Anomaly_Detection (Apache-2.0) | twice a second per camera |
| Fall detector | `melihuzunoglu/human-fall-detection` (AGPL-3.0) | once a second per camera |
| Violence classifier | `jaranohaal/vit-base-violence-detection` (Apache-2.0), loaded with timm | once a second per camera |
| Zero-shot scene model | `google/siglip-base-patch16-224` (Apache-2.0) | every 2 s per camera; the prompts are ours |
| RTSP server | MediaMTX (MIT) | serves the simulated camera streams |
| Video tooling | FFmpeg | loops clips into RTSP, encodes evidence clips |
| UI building blocks | React, Tailwind, Radix primitives, Recharts, lucide icons | the dashboard is assembled from these; layout and components are ours |

## Trained by us

| Model | Data | Script | Result file |
|---|---|---|---|
| Crowd-anomaly temporal CNN | UMN Unusual Crowd Activity, split by scene | `training/train_crowd.py` | `docs/results/crowd_model.json` |

| ML verifier per incident type | UCF-Crime annotated clips (Arson, Explosion, Fighting, Robbery, Shooting, RoadAccidents, Vandalism, Normal, ...), split by clip | `training/extract_features.py`, `training/train_verifiers.py` | `docs/results/verifiers.json` |

The crowd model's features (people count, share of moving pixels, flow magnitude, direction
entropy, per-person speed, change in count) come from our own `CrowdFeatures` class. The
verifiers' features come from our rule engines (for example: violence score, number of
people, distance between the closest two, whether a weapon was seen, scene-model margins).

## Written by us

| Area | Files | What it does |
|---|---|---|
| Ingestion | `backend/app/runtime.py` (`Worker`) | one thread per camera, RTSP with auto-reconnect or a looping file, about 10 fps sampling, 10 s ring buffer |
| Pipeline | `backend/app/runtime.py` (`Pipeline`), `backend/app/detector.py` | detect every other frame, track, run engines, annotate, stream |
| Model scheduler | `backend/app/aux_models.py` | one thread runs the six extra models across all cameras, each at its own rate, oldest request first, on the Apple GPU / CUDA / CPU |
| Six new engines | `backend/app/engines/extra.py` | fire, weapon, violence, medical, hazard, security: rules over detections that propose candidates and record features |
| ML verifier | `backend/app/intel/verifier.py` | per-type logistic regression over the rule features; decides instead of the rule gate and explains each decision |
| Accident engine | `backend/app/engines/accident.py` | model hits, a vehicle-presence check on each hit, a trajectory rule as second opinion and fallback |
| Crowd engine | `backend/app/engines/crowd.py` | feature extraction, the temporal CNN, overcrowding limit, motion z-score fallback |
| Baggage engine | `backend/app/engines/baggage.py` | bag memory by position, owner assignment, owner-away timer, tracker-ID handover |
| False-alarm filter | `backend/app/intel/filter.py` | persistence, ignore zones, camera agreement, then the ML verifier (or the rule gate where no verifier is trained); logs everything it suppresses |
| Severity | `backend/app/intel/severity.py` | 0-100 score where every point has a written reason |
| Incident manager | `backend/app/intel/incidents.py` | SQLite incidents, cross-camera merge by area and time, operator Confirm / Dismiss that moves the gate |
| Evidence | `backend/app/runtime.py` | keyframe and an H.264 clip cut from the ring buffer |
| API | `backend/app/main.py` | REST, event WebSocket, binary video WebSocket, MJPEG fallback |
| Dashboard | `frontend/src/` | command view, incident detail, cameras, zone editor, analytics, models page |
| Demo mode | `training/prepare_demo.py`, `backend/app/runtime.py` | replays cached detections in sync with the video |
| Evaluation | `training/bench/`, `training/eval_e2e.py` | the bench harness and the end-to-end numbers in BENCH.md |
| Tests | `backend/tests/`, `frontend/scripts/ui_check.mjs` | backend tests for every engine, the filter, the verifier, severity and merge; browser interaction checks |
| macOS support | `scripts/*.sh`, `backend/requirements-mac.txt` | setup, demo, live and stop scripts; Apple GPU selected automatically |

## Ideas borrowed (re-implemented, not copied)

See the table in CREDITS.md. In one line each:

- Owner-proximity test for bags: common to the four baggage repos we read.
- "Overlapping vehicles plus a sudden stop" as a collision cue: neyvur/traffic-video-analysis and kircova/Car-Crash-Detection.
- Exporting YOLO to OpenVINO for CPU CCTV work: saadkhan2003/CCTV_Video_Anomaly_Detection.

## What the bench changed in our plan

- We expected to reuse a repo's crowd logic. The count rule we benched flagged calm crowds
  and missed every dispersal on UMN, so we trained a temporal model instead.
- We expected the small accident model to be the obvious pick. It found more clips but has
  no licence, so the licensed YOLO11x model ships and the nano is left as a documented swap.
- COCO weights turned out to see parked bags poorly on ABODA. The baggage engine therefore
  remembers bags by position and tolerates gaps, and a luggage fine-tune notebook is ready.

- The violence model's Hugging Face checkpoint is stored in timm format under a transformers
  config; loaded the documented way it silently gives a random classifier. We load it with
  timm and checked which output means "violent" on fight footage.
- OpenAI CLIP and LAION OpenCLIP model cards rule out surveillance use, so the zero-shot
  scene model is SigLIP (Apache-2.0).

Figures behind each of these statements are in BENCH.md.
