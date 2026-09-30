# CREDITS.md

## Libraries and tools we ship or depend on

| Component | Version | Licence | Used for |
|---|---|---|---|
| Ultralytics YOLO | 8.4.168 | AGPL-3.0 | detection (YOLO11n COCO weights), ByteTrack implementation, OpenVINO export |
| OpenVINO | 2026.4.0 | Apache-2.0 | CPU inference for the COCO detector |
| PyTorch (CPU) | 2.14.0 | BSD-3-Clause | accident model inference, crowd model training and inference |
| OpenCV | 5.0.0 | Apache-2.0 | video I/O, optical flow, drawing |
| FastAPI, Uvicorn | see `backend/requirements.txt` | MIT, BSD-3-Clause | API and WebSockets |
| React, Vite, Tailwind CSS, Radix UI, TanStack Query, Recharts, lucide-react, sonner | see `frontend/package.json` | MIT / ISC | dashboard |
| Inter, JetBrains Mono (via Fontsource) | 5.3.0 | SIL OFL 1.1 | dashboard fonts, bundled so the UI works offline |
| MediaMTX | v1.21.1 | MIT | RTSP server for the simulated cameras (`tools\`, not committed) |
| FFmpeg (gyan.dev essentials build) | 9.0.2 | GPL-3.0 build | clip preparation, RTSP publishing, evidence clips (`tools\`, not committed) |

Because Ultralytics is AGPL-3.0, this project as a whole must be shared under
AGPL-3.0-compatible terms.

## Model weights

| Weights | Source | Licence | In the repo? |
|---|---|---|---|
| `yolo11n.pt` (COCO) | Ultralytics release assets | AGPL-3.0 | downloaded on first run, gitignored |
| `models/accident.pt` | Hugging Face `Enos-123/traffic-accident-detection-yolo11x`, file `weights/epoch61.pt`, revision `cdc556d278` | MIT (model card) | gitignored (114 MB); copy it from the link |
| `models/crowd_tcn.pt` | trained by us (`training/train_crowd.py`) on UMN | ours | gitignored, rebuilt by the script |

## Datasets (bench, training, demo clips; none are committed)

| Dataset | Used for | Source | Licence note |
|---|---|---|---|
| UCF-Crime (RoadAccidents, Testing_Normal) | accident bench, normal clips, demo cam1/cam2 | Sultani, Chen, Shah, CVPR 2018; Hugging Face mirror `AllenXeon/ucf_crime` | research dataset; mirror labels it CC0-1.0 |
| UMN Unusual Crowd Activity | crowd model training and bench, demo cam4 | University of Minnesota, `mha.cs.umn.edu` | research use; no licence text published |
| ABODA | baggage bench, demo cam3 | `kevinlin311tw/ABODA` (Lin et al.) | no licence file; research dataset |

## Reference repos: what we took

No file from any reference repo is copied into this project. Ideas we re-implemented:

| Idea | Seen in | Our implementation |
|---|---|---|
| Bag is "attended" while a person is within a distance of it; escalate with time unattended | BariaHarshh/CCTV-Surveillance-System (`features/abandoned_object`), TheRomanFour/AbandonedLuggageDetection, Kevinjoythomas/Unattended-Baggage-Detection, CostiCatargiu/NewLuggageDataset README | `backend/app/engines/baggage.py` (adds owner identity, owner-away verification, position-based bag memory, tracker-ID handover) |
| Collision = two tracked vehicles close together with a sudden loss of speed | neyvur/traffic-video-analysis (`src/events.py`), kircova/Car-Crash-Detection | `backend/app/engines/accident.py`, `_rule` |
| Crowd alert on sustained head count | BariaHarshh/CCTV-Surveillance-System (`features/crowd_detection`) | overcrowding limit in `backend/app/engines/crowd.py` |
| YOLO exported to OpenVINO for CPU CCTV inference | saadkhan2003/CCTV_Video_Anomaly_Detection | `training/export_models.py` |

Licences of those repos are listed in DISCOVERY.md. Several have no licence file, which
is why nothing from them is shipped.
