# DATASETS.md

Every dataset used for training or evaluation, where it came from, its licence, and whether
we have it. Files live under `data/` (not in git). "Labels" means time-stamped event labels
unless stated otherwise. No dataset terms were accepted through a browser in this run.

## Accident (CCTV viewpoint only)

| Dataset | Source | Licence | Size | Clips | Label type | Status |
|---|---|---|---|---|---|---|
| UCF-Crime RoadAccidents + Normal (test split) | Hugging Face mirror `AllenXeon/ucf_crime`; annotations `Temporal_Anomaly_Annotation_for_Testing_Videos.txt` | research dataset; mirror labels it CC0-1.0 | ~1.6 GB used | 23 accident + 25 normal (+ other classes as negatives) | start/end frame per anomaly | downloaded (`data/bench/_raw/ucf_more`, `ucf_road`) |
| Team's own videos | `E:\Downloads\1.mp4`, `2.mp4`, `3.mp4` | team's own | 12.5 MB | 3 | onset given by the team: 0:04, 0:05, 0:22 | copied to `data/custom` |
| NVIDIA PhysicalAI-Traffic-Anomaly-Reasoning (AI City 2026 Track 3) | huggingface.co/datasets/nvidia/PhysicalAI-Traffic-Anomaly-Reasoning, rev `8e905ef4f2` | CC-BY-4.0 | 4.3 MB of labels | 3,670 labelled events over 8 source sets | start/end timestamps per event (`train/temporal_localization.json`), natural-language question per event | labels downloaded (`data/raw/nvidia_traffic`); videos come from the sources below |
| TADBench (UnicomAI) | Google Drive file `14GNlNcWLzN-sbzvmrMuSbAg_rZZ5yd26`, linked from github.com/UnicomAI/UnicomBenchmark/tree/main/TADBench | not stated (repo has no licence file) | 4.2 GB | 366 labelled clips in the NVIDIA labels | class folder per clip + NVIDIA timestamps | downloading (`data/raw/tadbench`) |
| TAD (Traffic Anomaly Dataset) | Kaggle `nikanvasei/traffic-anomaly-dataset-tad` | not stated on Kaggle | 13.4 GB (JPEG frames) | 191 labelled | NVIDIA timestamps | **blocked: over the 5 GB cap, and Kaggle serves it as one archive, so no subset is possible** |
| SO-TAD | huggingface.co/datasets/cccccxy/so-tad | not stated | ~12+ GB, 24+ parts of a split zip | 2,185 labelled | NVIDIA timestamps | **blocked: over the 5 GB cap; a split zip cannot be partially extracted** |
| HTV (Highway Traffic Videos) | Kaggle `aryashah2k/highway-traffic-videos-dataset` | not stated | 92 MB | 254 normal highway clips (hard negatives) | NVIDIA timestamps of normal events | **blocked: needs a Kaggle download; Chrome froze (machine out of memory). See SIGNUP_NEEDED.md** |
| ACCIDENT @ CVPR 2026 benchmark | kaggle.com/competitions/accident | competition rules | not checked | real-CCTV test set is hidden | temporal, spatial, collision type | **blocked: needs joining a Kaggle competition. See SIGNUP_NEEDED.md** |
| CADP | YouTube-sourced | research | - | - | - | skipped (time; videos must be scraped from YouTube) |
| DoTA, A3D | - | - | - | - | - | excluded on purpose: dashcam viewpoint |

## Crowd

| Dataset | Source | Licence | Size | Clips | Label type | Status |
|---|---|---|---|---|---|---|
| MED (Motion Emotion Dataset) | Dropbox link in github.com/hosseinm/med (`med_get.sh`) | research use (AVSS 2016 paper); no licence file | 276 MB | 31 videos | per-frame behaviour label: panic, fight, congestion, obstacle, neutral (`dataset_frames_abnormal_labeling.m`) | downloaded (`data/raw/med`) |
| UMN Unusual Crowd Activity | mha.cs.umn.edu | research use | 25 MB | 11 scenes | per-frame abnormal flag (read from the burnt-in caption) | downloaded earlier (`data/bench/crowd`) |
| UCSD Ped2 | official site svcl.ucsd.edu (Kaggle copy not needed) | research use | 740 MB archive (Ped1+Ped2) | Ped2: 16 train, 12 test | per-frame anomaly flags for the test clips (non-pedestrian entities: bikes, carts) | downloaded and Ped2 extracted (`data/raw/ucsd`) |

## Baggage

| Dataset | Source | Licence | Size | Clips | Label type | Status |
|---|---|---|---|---|---|---|
| ABODA | github.com/kevinlin311tw/ABODA | no licence file | 260 MB | 11 | one abandonment per video; no timestamps shipped | downloaded earlier (`data/bench/_raw/ABODA`) |
| AVSS 2007 (i-LIDS left baggage), via the UAM AOD survey | www-vpu.eps.uam.es/publications/AODsurvey/ (AbandonedObjectDetection-CODE.zip) | research use | 975 MB zip, 3 videos used | 3 (easy, medium, hard) | ViPER XML: PutObject and AbandonedObject frame spans + boxes | downloaded (`data/raw/uam_aod/datasets/AVSS2007`) |
| PETS 2006 | www.cvg.reading.ac.uk/PETS2006/ | research use | - | - | - | **blocked: site did not respond (http and https)** |
| Roboflow `drone-analysis/abandoned-bags-2afuo` and the luggage sets in TheRomanFour/AbandonedLuggageDetection | Roboflow Universe | per dataset | - | - | YOLO boxes | **blocked: needs a Roboflow API key or a signed-in browser download. See SIGNUP_NEEDED.md** |

## Status update, overnight 2026-10-01

- TADBench: downloaded (4.5 GB) and unzipped to `data/raw/tadbench/TAD-benchmark` (372 train + 32 test videos);
  291 of its accident clips are timed by the NVIDIA AI City 2026 Track 3 labels.
- UCSD Ped2: extracted; 12 test clips with anomaly frame spans.
- MED: 31 videos; behaviour spans parsed from `dataset_frames_abnormal_labeling.m`.
- AVSS 2007: easy / medium / hard with PutObject and AbandonedObject frame spans; used as the untouched baggage
  frozen test.
- Unified labels: `data/labels/accident_events.csv` (519 events and normal rows: UCF-Crime, TADBench, team videos),
  `crowd_events.csv` (64: MED, UCSD Ped2, UMN), `baggage_events.csv` (12: AVSS 2007, ABODA), split by video.
  Built by `training/unify_labels.py`. Not yet used for training: there was no GPU time (no Kaggle token, see
  SIGNUP_NEEDED.md) and the night went to the evaluation harness.
