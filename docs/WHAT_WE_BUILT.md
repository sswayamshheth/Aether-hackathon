# What we built, and what we took

For judge questions. Short version: the detector weights are pretrained and credited; the
pipeline around them, the three engines, the crowd model, the incident layer and the
dashboard are ours. No source file from another project is copied into this repo.

## Taken as-is (pretrained or off the shelf)

| Piece | From | How it is used |
|---|---|---|
| Object detector | Ultralytics YOLO11n, COCO weights (AGPL-3.0) | people, vehicles and bags on every camera, exported by us to OpenVINO |
| Tracker | ByteTrack as implemented in Ultralytics | one tracker instance per camera, for people and vehicles |
| Accident detector | `Enos-123/traffic-accident-detection-yolo11x` on Hugging Face (MIT) | second model, run about once a second on traffic cameras |
| RTSP server | MediaMTX (MIT) | serves the simulated camera streams |
| Video tooling | FFmpeg | loops clips into RTSP, encodes evidence clips |
| UI building blocks | React, Tailwind, Radix primitives, Recharts, lucide icons | the dashboard is assembled from these; layout and components are ours |

## Trained by us

| Model | Data | Script | Result file |
|---|---|---|---|
| Crowd-anomaly temporal CNN | UMN Unusual Crowd Activity, split by scene | `training/train_crowd.py` | `docs/results/crowd_model.json` |

The features it consumes (people count, share of moving pixels, flow magnitude, direction
entropy, per-person speed, change in count) are computed by our own
`CrowdFeatures` class from our detector and tracker output.

## Written by us

| Area | Files | What it does |
|---|---|---|
| Ingestion | `backend/app/runtime.py` (`Worker`) | one thread per camera, RTSP with auto-reconnect or a looping file, about 10 fps sampling, 10 s ring buffer |
| Pipeline | `backend/app/runtime.py` (`Pipeline`), `backend/app/detector.py` | detect every other frame, track, run engines, annotate, stream. The slow accident model runs on its own thread so it cannot stall the cameras |
| Accident engine | `backend/app/engines/accident.py` | model hits, a vehicle-presence check on each hit, a trajectory rule as second opinion and fallback |
| Crowd engine | `backend/app/engines/crowd.py` | feature extraction, the temporal CNN, overcrowding limit, motion z-score fallback |
| Baggage engine | `backend/app/engines/baggage.py` | bag memory by position, owner assignment, owner-away timer, tracker-ID handover |
| False-alarm filter | `backend/app/intel/filter.py` | persistence, confidence gate, ignore zones, camera agreement; logs everything it suppresses |
| Severity | `backend/app/intel/severity.py` | 0-100 score where every point has a written reason |
| Incident manager | `backend/app/intel/incidents.py` | SQLite incidents, cross-camera merge by area and time, operator Confirm / Dismiss that moves the gate |
| Evidence | `backend/app/runtime.py` | keyframe and an H.264 clip cut from the ring buffer |
| API | `backend/app/main.py` | REST, event WebSocket, binary video WebSocket, MJPEG fallback |
| Dashboard | `frontend/src/` | command view, incident detail, cameras, zone editor, analytics, models page |
| Demo mode | `training/prepare_demo.py`, `backend/app/runtime.py` | replays cached detections in sync with the video |
| Evaluation | `training/bench/`, `training/eval_e2e.py` | the bench harness and the end-to-end numbers in BENCH.md |
| Tests | `backend/tests/test_intel.py`, `frontend/scripts/ui_check.mjs` | 27 backend tests for the engines, filter, severity and merge; 11 browser interaction checks |

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

Figures behind each of these statements are in BENCH.md.
