# STATUS.md - read this first

Written 2026-09-30, end of the autonomous build. Everything below was checked on this
machine unless it says otherwise.

## The short version

The product runs end to end. One command brings up four simulated RTSP cameras, live
detection, and the dashboard in Chrome; all three incident types appear with severity and
reasons, and the accident is merged across two cameras. Demo mode does the same offline
from cached detections.

The weak spot is accident detection: **1 of 8** bench accidents detected end to end. Crowd
is strong on its (staged) dataset, **10 of 11**; baggage is **3 of 6**. Do not quote an
accuracy figure in the pitch. BENCH.md has every number with its clip count.

## Data and training (overnight 2026-10-01) - read OVERNIGHT_REPORT.md first

- **Downloaded:** TADBench (4.5 GB, 404 videos), MED (31), UCSD Ped2, AVSS 2007 (3, with UAM ground truth), the
  NVIDIA AI City 2026 traffic-anomaly labels. **Blocked:** TAD and SO-TAD (over the 5 GB cap), HTV, the Roboflow
  luggage sets and the CVPR ACCIDENT benchmark (need your login or API key), PETS 2006 (site down). Details in
  DATASETS.md and SIGNUP_NEEDED.md.
- **Labels unified:** `data/labels/{accident,crowd,baggage}_events.csv`, split by video (`training/unify_labels.py`).
- **Models improved:** none promoted. The accident classifier (SigLIP + logistic regression) was retrained with the
  frozen test held out and caught 1 of 7 frozen-test accidents; it stays in `models/candidates/`. No YOLO fine-tune
  ran: no Kaggle token, no GPU on this laptop.
- **Logic candidates** (behind switches, stable defaults unchanged): `DRISHTI_ACCIDENT_RULE=abrupt`,
  `DRISHTI_LOITER_CONF=0.65` with `DRISHTI_LOITER_WINDOW_S=30`, `DRISHTI_CROWD_FLOW_MAX=0.8`. Why none passed the
  promotion gate: OVERNIGHT_LOG.md.
- **Retrain / re-evaluate:**

```powershell
cd E:\sss\study\btech\aether-hackathon
backend\.venv\Scripts\python training\extract_features.py           # model outputs for the UCF clips (slow on CPU)
backend\.venv\Scripts\python training\real_eval.py --build-tracks   # detector caches for UMN / ABODA / AVSS
backend\.venv\Scripts\python training\real_eval.py --split test      # frozen test: never tune on it
backend\.venv\Scripts\python training\real_eval.py --split val,demo  # validation + demo_eval
$env:ACC_CLF_CACHED_ONLY='1'; backend\.venv\Scripts\python training\train_accident_clf.py
backend\.venv\Scripts\python training\unify_labels.py
backend\.venv\Scripts\python training\synth\make_scenarios.py
backend\.venv\Scripts\python training\synth\run_suite.py --workers 2
```

- Tests: 48 pass (`backend\tests\test_overnight.py` covers the new switches).

## Run it

```powershell
cd E:\sss\study\btech\aether-hackathon

# Demo mode (use this on stage): cached detections, no YOLO inference, no internet
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1

# Live mode: MediaMTX + ffmpeg publish rtsp://localhost:8554/cam1..cam4, real inference
powershell -ExecutionPolicy Bypass -File scripts\start.ps1

# Stop whichever is running
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
```

Both open http://localhost:8000 in Chrome. In demo mode the accident appears about 10 s
in, the crowd incident about 20 s in, the abandoned bag about 50 s in.

To try your own source: Cameras page, paste an RTSP URL (for example
`rtsp://localhost:8554/cam1` while live mode is running) or drop a video file.

Tests: `cd backend; .venv\Scripts\python -m pytest tests -q` (27 pass).

## What works

| Thing | How it was checked |
|---|---|
| `start.ps1`: 4 RTSP cameras online with live inference | run from PowerShell; 4.9 fps per camera on a quiet machine, 3.7 when busy |
| Accident, crowd and baggage incidents with severity and reasons | seen in live mode and demo mode |
| Cross-camera merge | accident on cam1 + cam2 became one Critical incident, in both modes |
| Evidence clip and keyframe per incident | clips written and played in the incident page |
| Video upload as a camera | uploaded an ABODA clip through the API; online at 10 fps with boxes |
| Confirm / Dismiss moving the gate | dismissing a baggage incident moved that camera's gate from 0.18 to 0.23 |
| Zones | drew, saved and deleted a zone with the mouse in Chrome (`frontend\scripts\ui_check.mjs`); filter behaviour covered by tests |
| Demo mode | 4 cameras at 10 fps from cached detections; the two YOLO models are not loaded (the small crowd model still runs, on cached tracks) |
| Keyboard triage, click-to-focus, form validation | 11 interaction checks pass in Chrome (`frontend\scripts\ui_check.mjs`) |
| Demo mode offline | the demo backend held no non-local network connections and the built dashboard loads nothing from a CDN (fonts are bundled). Not tested with the network physically switched off |
| Dashboard | every screen screenshotted in Chrome at 1440 and 1920 and reviewed over three rounds, no console errors (`docs\screenshots\`) |

## What is partial

- **Accident detection.** Works on the demo clip and one other bench clip. Misses the
  rest and sometimes fires before the annotated onset. Both pretrained accident models we
  found behave this way on low-resolution CCTV (BENCH.md).
- **Live accident alerts lag.** The accident model is a YOLO11x taking about 1.4 s per
  frame on this CPU. It runs on a side thread, so cameras keep going, but an accident
  shows up several seconds late in live mode. Demo mode hides this; say so if asked.
- **Baggage** depends on the COCO detector seeing the bag, which it often does not.
- **Vision verification and Telegram** are built, off by default, and have never run
  against the real services (no keys). Vision verification was only exercised with an
  invalid key, where it fails safe.
- **Live RTSP loops** repeat the same footage, so an ongoing incident's "not cleared for
  N s" keeps growing. That is the simulation, not a bug in the timer.

## What was cut

| Cut | Why |
|---|---|
| Kaggle fine-tunes (accident, luggage) | no `kaggle.json` and no Roboflow key. Notebooks are written, not run |
| M4 learned severity model | too little data to beat the rule-based score honestly |
| Re-ID across cameras, WebRTC, light theme | nice-to-haves, time |
| One venv per reference repo | one shared reference venv instead (DECISIONS.md #5) |

## Manual steps still open

1. **Kaggle notebooks** (optional, about 1 hour of GPU each): upload
   `training\kaggle\accident_yolo11n.ipynb` to kaggle.com in Chrome, set Accelerator to
   GPU T4, turn Internet on, add a secret `ROBOFLOW_API_KEY` (free Roboflow account), Run
   All, download the `.pt` and metrics file. The last notebook cell says how to bench the
   result against the current model before adopting it. Same for `luggage_yolo11n.ipynb`.
2. **Telegram**: set `TELEGRAM_ENABLED=1`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in `.env`.
3. **Vision verification**: set `VISION_VERIFY_ENABLED=1` and `ANTHROPIC_API_KEY` in `.env`.
   It sends three head-blurred frames per incident to the API, so it costs money per incident.
4. **Check the pitch deck against this file.** I have not seen the deck. If it says any
   detector was fine-tuned by the team, that is not true yet: the only model we trained is
   the crowd model.

## Top 3 things to fix next

1. **Accident recall.** Run the accident notebook, bench it with
   `training\bench\run_bench.py accident_weights`, and keep it only if it beats 1 of 8 end
   to end. A nano model would also remove the live lag.
2. **Bag detection.** Run the luggage notebook and wire the weights in as a second
   detector if they beat COCO on ABODA (COCO sees a bag in 27% of sampled frames).
3. **A bigger, untouched evaluation set.** The crowd persistence setting was adjusted
   after looking at this one. Add clips nobody has tuned on before quoting any rate.

## Things you should know

- **Licences.** None of the six repos in the brief has a licence file. Nothing from them
  is copied or shipped; ideas are credited in CREDITS.md. Ultralytics is AGPL-3.0, so the
  repo has to be shared under compatible terms.
- **cam2 is simulated**: cam1's clip mirrored and cropped. Say so on stage.
- **Not in git**: `data\`, `models\*.pt`, `tools\`, `_reference\`. The project only runs
  on this machine until those are copied or rebuilt (README, Setup).
- **Memory.** The laptop was at 24 to 27 GB of 28 GB commit during the build, with your
  other apps running. Close what you can before a demo.
- **One file outside the project was touched**: importing Ultralytics updated its own
  settings file at `%APPDATA%\Ultralytics\settings.json` on first import. Later runs use
  `.cache\ultralytics` inside the project.
- **One request went to api.anthropic.com** with a deliberately invalid key, to confirm
  the verification code fails safely. No real key was used or looked for.
- Your other running apps (port 8090 and the rest) were not touched.

## Where things are

| File | What |
|---|---|
| BENCH.md | every measurement, generated from `docs\results\*.json` |
| DISCOVERY.md | repo survey, licences, install-script review |
| DECISIONS.md | 19 decisions taken without you, with reasons |
| docs\WHAT_WE_BUILT.md | ours versus borrowed, for judges |
| docs\PITCH_NOTES.md | ten likely questions with honest answers |
| PROGRESS.md | the checklist |
