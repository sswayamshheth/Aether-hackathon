# OVERNIGHT_REPORT.md - 2026-10-01, 03:42 to 08:00

**Short version:** the app is unchanged in behaviour and still runs (48 tests pass, smoke test passes). Tonight built
the tools to measure it honestly: a 650-scenario synthetic suite, a real-footage evaluation with a frozen test, and
unified labels for 7 datasets. Three logic fixes were made and tested. All three sit behind config switches, and
**none passed the promotion gate**, so the stable logic is still the default. The most useful fix to turn on is
loitering (stable loitering can never fire). Details below. Every number is from a script run tonight; synthetic and
real results are kept separate.

## 1. Real metrics, start of night vs end of night (REAL footage)

Nothing was promoted, so the end-of-night system is the start-of-night system. The table shows its numbers on the
complete caches, plus the best candidate for comparison.

| Frozen test (never tuned on) | Stable (default) | Best candidate | Candidate |
|---|---|---|---|
| Accident, UCF-Crime 7 clips | **4/7** detected, 2 early, 2 false alarms (8.4 / camera-hour) | 3/7, 2 early, 1 false alarm (4.2 / h) | `ACCIDENT_RULE=abrupt` |
| Crowd, UMN scenes 1 4 7 9 | **3/4**, median delay 1.5 s | 3/4 (same) | `CROWD_FLOW_MAX=0.8` |
| Baggage, AVSS 2007 easy/medium/hard | **2/3**, 0 false alarms, 22.9 s after put-down | 2/3 (same) | - |
| Crowd false alarms on other test clips | 2 on AVSS videos, 3 on UCF clips | same | - |

| demo_eval (the 4 demo cameras) | Stable | Candidates |
|---|---|---|
| accident (cam1 + mirrored cam2) | 1/2 | 1/2 |
| crowd (cam4) | 1/1 | 1/1 |
| baggage (cam3) | **0/1** | 0/1 |

**Read this before the demo:** the demo bag (cam3) is found but suppressed: "confidence 0.21 below gate 0.40". The
baggage gate went from 0.18 to 0.40 in the "better ML" commit (`GATE["baggage"]` in `backend/app/config.py`). Putting
it back to about 0.18 restores the demo alarm. The cost: synthetic "bin/box/stroller seen as a bag" traps (detector
confidence 0.20-0.45) would alarm more often. This is a call for you and your friend; I did not change it.
Also: the demo baggage alarm (cam3) and the cam2 accident no longer fire in replay. On
30 Sep both fired (`docs/results/demo_run.json`). The change came with the "better ML" commit on main (stricter
gates), not with tonight's work. Re-check `scripts\demo.ps1` before going on stage. If the bag still does not
appear, the gate values in `backend/app/config.py` (`GATE`, `PERSIST_S`, `MIN_HITS`) are where to look.

Validation split (tuning allowed): accident 5/16 for both rules; false alarms 4 (stable) vs 0 (abrupt).
Files: `docs/results/real_eval_acc_v1.json`, `real_eval_acc_abrupt.json`, `real_eval_baseline_test.json`,
`real_eval_baseline_demo.json`, `real_eval_it23_*.json`.

## 2. Synthetic suite results (SYNTHETIC, method A = logic only, models silent)

Full baseline, 650 scenarios (`docs/results/synthetic_suite_baseline.json`):

| Family | Scenarios | Pass rate | Precision | Recall | F1 | Trap false alarms / camera-hour |
|---|---|---|---|---|---|---|
| accident + traffic anomalies | 230 | 0.47 | 0.49 | 0.46 | 0.47 | 56.7 |
| crowd | 150 | 0.53 | 0.71 | 0.33 | 0.46 | 21.2 |
| baggage | 150 | 0.81 | 0.97 | 0.71 | 0.82 | 2.2 |
| other (loiter, intrusion, fall) | 30 | 0.33 | 1.00 | 0.33 | 0.50 | - |
| system (reconnect, low fps, multi-camera) | 80 | 0.65 | 1.00 | 0.70 | 0.82 | - |

Stable vs all candidate switches, on the same scenarios (variants 1-5 of every case, 325 scenarios,
`synthetic_suite_final_candidates.json`):

| Family | Pass, stable -> candidates | Trap false alarms |
|---|---|---|
| accident | 55 -> 67 of 115 | 25 -> 12 |
| crowd | 40 -> 44 of 75 | 6 -> 2 |
| other | 5 -> 10 of 15 | - |
| baggage | 59 -> 59 of 75 | 0 -> 0 |
| system | 27 -> **19** of 40 | - (the abrupt rule misses crashes at low fps and across camera views) |

Method B (pixel-level variants of the real demo clips, full detector): 12 image conditions per clip, through YOLO11n +
ByteTrack + engines (`docs/results/synthetic_pixel_{crowd,accident,baggage}.json`):

| Clip | Passed | Survives | Fails |
|---|---|---|---|
| crowd, UMN scene 4 | 7/12 | reference, night, fog, JPEG q10, infrared, dropped frames, occlusion mask | rain, low resolution, motion blur, shake (early alarm), noise |
| accident, UCF RoadAccidents010 | 5/12 | reference, fog, infrared, dropped frames, occlusion mask | night, rain, JPEG q10, low resolution, motion blur, shake, noise |
| baggage, ABODA video 9 | 0/12 | none: the bag is found, but its confidence (mean 0.21) is under the 0.40 gate, the same cause as the demo_eval miss below | all, including the unmodified clip |

Every scenario with its expected outcome: SYNTHETIC_SCENARIOS.md. Failure clusters: ERRORS.md.

## 3. Top 5 fixes (all behind switches)

1. **Loitering could never fire.** It emitted 0.55 under a 0.60 gate, and it measured spread over the whole track,
   including the walk into view. `DRISHTI_LOITER_CONF=0.65`, `DRISHTI_LOITER_WINDOW_S=30`: synthetic 0/10 -> 5/5.
   No real loitering labels exist. **Recommended to switch on.**
2. **Accident rule fired on normal braking.** Queues, red lights, perspective overlap, crowd crossing and camera shake
   made up 53 of the 66 synthetic trap false alarms. `abrupt` needs an impact-like stop and the pair closing in.
   Real validation false alarms 4 -> 0, but it lost one frozen-test accident (4/7 -> 3/7), so it was not promoted.
3. **Single-vehicle crashes had no rule** (skid, pole, rollover, pedestrian hit: 0/40). Part of `abrupt`.
4. **Overcrowding fired on processions and train-arrival rushes**, at Critical severity. `CROWD_FLOW_MAX=0.8` only
   counts a packed crowd: crowd-trap false alarms 6 -> 2, no change on real footage.
5. **Harness bugs fixed before they could mislead:** synthetic braking was scripted as a sudden two-step stop, which
   looked like a crash and made the first version of fix 2 look better than it was.

## 4. What was promoted, what was kept stable

| Item | Decision | Why |
|---|---|---|
| Accident rule `abrupt` | kept stable `v1` | frozen-test recall 4/7 -> 3/7 (gate: equal or better); system scenarios regress |
| Loitering switches | kept stable | no real loitering footage, demo_eval unchanged (gate asks for "better on demo_eval"); recommended anyway, since stable loitering can never fire |
| Crowd flow check | kept stable | real and demo unchanged; same reasoning |
| Accident classifier | candidate only (`models/candidates/accident_clf.json`) | 1/7 on the frozen test, 0/3 on your own videos |
| Verifiers (`train_verifiers.py`) | not trained tonight | the extraction it needs finished at 06:44; no time to train and gate it |

To try the candidates: `$env:DRISHTI_LOITER_CONF='0.65'; $env:DRISHTI_LOITER_WINDOW_S='30'` (and/or
`$env:DRISHTI_ACCIDENT_RULE='abrupt'`, `$env:DRISHTI_CROWD_FLOW_MAX='0.8'`) before `scripts\start.ps1`, or put them
in `.env`.

## 5. Known weaknesses

- **Accident recall on real CCTV is low:** 4/7 on the frozen test, 5/16 on validation, with early alarms. Fine-tuning
  needs a GPU (Kaggle notebooks are ready; SIGNUP_NEEDED.md lists the token step).
- **Crowd motion on synthetic scenes:** panic, surge, sudden running, counter-flow and fight score 0-2/10 in method
  A, because the crowd model was trained on real UMN video, not rendered rectangles. It scores 3/4 on real held-out
  UMN. Method A crowd numbers measure the rules, not the model.
- **Medical (collapse, fall):** the lying-person rule alone emits 0.35, under the 0.80 gate, so without the fall
  model it never raises (method A: 0/10 and 0/10).
- **No semi-/unsupervised phase was reached** (pseudo-labelling, normality models, consistency checks). The night
  went to building a trustworthy judge (frozen test, cache replay) and the suite. The CPU-only laptop ran 4-5 jobs at
  once, and one suite run (35 min) was lost to a harness crash, now fixed.
- **Method C** (composited baggage scenes) was not built. Baggage timing cases are covered by method A.
- 13 of the 650 scenarios (surge x10 in the baseline) hit a harness error, which was fixed afterwards.

## 6. Commands

```powershell
cd E:\sss\study\btech\aether-hackathon
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1        # demo mode
powershell -ExecutionPolicy Bypass -File scripts\start.ps1       # live mode
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
cd backend; .venv\Scripts\python -m pytest tests -q; cd ..         # 48 tests

# scenario suite (method A): all 650, or one case / family, or a sample
backend\.venv\Scripts\python training\synth\make_scenarios.py
backend\.venv\Scripts\python training\synth\run_suite.py --workers 2 --tag mine
backend\.venv\Scripts\python training\synth\run_suite.py --only baggage --sample 3
backend\.venv\Scripts\python training\synth\pixel_variants.py      # method B
backend\.venv\Scripts\python training\synth\errors.py docs\results\synthetic_suite_mine.json
backend\.venv\Scripts\python training\real_eval.py --split test     # real frozen test
```

## 7. Git

All work was done on `overnight/2026-10-01`. At 07:15: fetched (no new commits from your friend on origin/main),
pulled main with `--ff-only`, merged the branch with a merge commit (no conflicts), re-ran the tests (48 pass) and
the smoke test on main (live mode, 1 camera online, dashboard 200). Then pushed `main` and
`overnight/2026-10-01` to github.com/sswayamshheth/Aether-hackathon. No force-push, no history rewritten. Model
weights and `data/` stay out of git; their hashes are in `models/MANIFEST.md`.

Also on the branch: a commit from 03:50 ("Phase A: dataset inventory and blocked downloads") made by the previous
session's last step after it was closed. It only adds DATASETS.md and SIGNUP_NEEDED.md.
