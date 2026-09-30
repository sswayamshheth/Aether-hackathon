# SIGNUP_NEEDED.md

Downloads the autonomous run could not do. Each needs you, a few clicks, and then the file
moved into the folder named. After that, rerun the step named in "then".

Why these were skipped: no `kaggle.json`, no `.env` with Hugging Face or Roboflow keys (I am
not allowed to create tokens), and Chrome froze when I tried to use it for downloads because
the laptop was out of memory (0.8 GB free, Chrome itself holding 5.4 GB).

| # | What | Where | What you do | Put it in | Then |
|---|---|---|---|---|---|
| 1 | HTV highway videos (92 MB, normal traffic, hard negatives for accidents) | https://www.kaggle.com/datasets/aryashah2k/highway-traffic-videos-dataset | Click **Download** (signed in to Kaggle) | unzip to `data\raw\htv\` | `training\prepare_labels.py` then retrain accident |
| 2 | ACCIDENT @ CVPR 2026 training data (CCTV accidents with temporal, spatial and collision-type labels) | https://www.kaggle.com/competitions/accident/data | Join the competition (accept its rules), then **Download All**. Check the size first: skip if over 5 GB | `data\raw\accident_bench\` | same as above |
| 3 | Roboflow abandoned bags (YOLO boxes) | https://universe.roboflow.com/drone-analysis/abandoned-bags-2afuo | **Download Dataset** > format **YOLOv11** > "download zip to computer" | `data\raw\roboflow_bags\` | bag detector fine-tune (needs a GPU; see STATUS.md) |
| 4 | Luggage datasets linked by TheRomanFour/AbandonedLuggageDetection | https://app.roboflow.com/cars-0jbgu/luggage-detection-axdmv/1 and https://app.roboflow.com/cars-0jbgu/luggage_2_dataset/2 | Same as 3 | `data\raw\roboflow_luggage\` | same as 3 |
| 5 | TAD (13.4 GB) and SO-TAD (12+ GB) | Kaggle `nikanvasei/traffic-anomaly-dataset-tad`, HF `cccccxy/so-tad` | Only if you raise the 5 GB-per-dataset cap and have the disk space | `data\raw\tad\`, `data\raw\so_tad\` | same as 1 |
| 6 | Kaggle GPU for fine-tuning | https://www.kaggle.com/settings > API > Create New Token | Save it as `%USERPROFILE%\.kaggle\kaggle.json` | - | the Kaggle notebooks in `training\kaggle\` |
| 7 | PETS 2006 left luggage | http://www.cvg.reading.ac.uk/PETS2006/ | The site did not respond. Try later, or find a mirror | `data\raw\pets2006\` | baggage threshold search |
