# CREDITS.md

## Libraries and tools we ship or depend on

| Component | Version | Licence | Used for |
|---|---|---|---|
| Ultralytics YOLO | 8.4.168 | AGPL-3.0 | detection (YOLO11n COCO weights), ByteTrack implementation, OpenVINO export |
| OpenVINO | 2026.4.0 | Apache-2.0 | CPU inference for the COCO detector |
| PyTorch | 2.14.0 | BSD-3-Clause | all non-OpenVINO inference; Apple GPU (MPS) on the Mac |
| timm | 1.0.30 | Apache-2.0 | loads the violence classifier (ViT-B/16) |
| Hugging Face transformers | 4.57.6 | Apache-2.0 | loads SigLIP for zero-shot scene scores |
| scikit-learn | 1.7.2 | BSD-3-Clause | training the ML verifiers only (the app reads the weights from JSON) |
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
| `models/verifiers.json` | trained by us (`training/train_verifiers.py`) on UCF-Crime | ours | gitignored, rebuilt by the script |
| `models/fire_smoke.pt` | Hugging Face `rabahdev/fire-smoke-yolov8n` (YOLOv8n on the D-Fire dataset), revision `13017fe8af` | AGPL-3.0 | gitignored; `training/get_models.py` |
| `models/weapon.pt` | `models/weapon_detector.pt` from github.com/saadkhan2003/CCTV_Video_Anomaly_Detection, commit `4ab4eb0349` | Apache-2.0 (repo LICENSE file) | gitignored; `training/get_models.py` copies it from `_reference\` |
| `models/fall.pt` | Hugging Face `melihuzunoglu/human-fall-detection`, revision `97261b0363` | AGPL-3.0 | gitignored; `training/get_models.py` |
| `models/violence_vit/` | Hugging Face `jaranohaal/vit-base-violence-detection`, revision `31931091df` | Apache-2.0 | gitignored; weights are in timm format despite the transformers config, so we load them with timm |
| `models/siglip/` | Hugging Face `google/siglip-base-patch16-224`, revision `7fd15f0689` | Apache-2.0 | gitignored; `training/get_models.py` |

We did not use OpenAI CLIP or LAION OpenCLIP for zero-shot scene scores: both model cards
state that surveillance use is always out of scope. SigLIP's card carries no such
restriction.

## Datasets (bench, training, demo clips; none are committed)

| Dataset | Used for | Source | Licence note |
|---|---|---|---|
| UCF-Crime (RoadAccidents, Testing_Normal) | accident bench, normal clips, demo cam1/cam2 | Sultani, Chen, Shah, CVPR 2018; Hugging Face mirror `AllenXeon/ucf_crime` | research dataset; mirror labels it CC0-1.0 |
| UMN Unusual Crowd Activity | crowd model training and bench, demo cam4 | University of Minnesota, `mha.cs.umn.edu` | research use; no licence text published |
| ABODA | baggage bench, demo cam3 | `kevinlin311tw/ABODA` (Lin et al.) | no licence file; research dataset |
| UCF-Crime (Arson, Explosion, Fighting, Assault, Abuse, Robbery, Shooting, Vandalism, Stealing, Burglary, more RoadAccidents and Normal) | training and cross-validating the ML verifiers; demo cam5 (fight) and cam6 (arson), both held out of training | same mirror as above | as above |

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
