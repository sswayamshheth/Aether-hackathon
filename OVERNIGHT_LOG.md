# OVERNIGHT_LOG.md - autonomous refinement run, 2026-10-01 (deadline 08:00 IST)

Newest entries at the bottom. Synthetic and real results are always reported separately.

## 03:42 start
- Clock read 03:42 IST (the prompt's 03:00 milestone had already passed; schedule shifted, order kept).
- Previous session (dataset acquisition, Phase A of the data brief) was cut off at 03:39 while unzipping TADBench.
  Survived: feature-extraction job (accident pass 29/48 clips), TADBench unzip, AVSS2007 / UCSD Ped2 / MED downloads.
- Protect the app: backend tests **44 passed**; smoke test `scripts\start.ps1 -NoBrowser -NoRtsp -Cams 1` -> `/api/status`
  answered (live mode, OpenVINO CPU, 1 camera online, 0.4 fps while two training jobs shared the CPU); stopped cleanly.
- Branch `overnight/2026-10-01` created from main after `git pull --ff-only` (friend's commits up to c32fe18 included).
- Stable models copied (not moved) to `models\stable\` (167 MB, gitignored).
- Found: `models/verifiers.json` and `models/accident_clf.json` do not exist, so the app currently runs on rule gates only.
- 03:51 restarted the SigLIP embedding job for the accident classifier with accident / custom / normal clips first
  (it was alphabetical and would have reached the accident clips after ~3 h). Clips already embedded (33) are reused.

## Baselines (start of night, stable logic, models as on main)
Synthetic method A, full suite, 650 scenarios (`docs/results/synthetic_suite_baseline.json`; SYNTHETIC, logic only, models silent):
| family | scenarios | pass rate | precision | recall | F1 | trap false alarms / camera-hour |
|---|---|---|---|---|---|---|
| accident (incl. traffic anomalies) | 230 | 0.465 | 0.488 | 0.462 | 0.474 | 56.7 |
| crowd | 150 (surge x10 = harness error) | 0.527 | 0.714 | 0.333 | 0.455 | 21.2 |
| baggage | 150 | 0.813 | 0.970 | 0.711 | 0.821 | 2.2 |
| other (loiter, intrusion, fall) | 30 | 0.333 | 1.0 | 0.333 | 0.5 | - |
| system | 80 | 0.65 | 1.0 | 0.70 | 0.824 | - |
| all | 650 | 0.569 | | | | |

Real frozen test (`docs/results/real_eval_baseline_test.json`; REAL footage, cached detections replayed):
accident 3/7 clips (1 early alarm, 2 false alarms, 5.9 / camera-hour); crowd UMN 3/4 (5 false alarms on other clips,
13.7 / camera-hour); baggage AVSS 2007 2/3 (0 false alarms, median delay 22.9 s after the bag was put down).
Real demo_eval (`real_eval_baseline_demo.json`): accident 1/2 cameras, crowd 1/1, baggage 0/1. (The 30 Sep demo run
had all four; the stricter gates in the "better ML" commit cost the cam2 accident and the bag alarm.)

Harness bugs found and fixed while building the baseline (not product changes): bag keyframes in the
handover / taken-by-stranger generators (crash), braking scripted as two linear segments (looked like an impact),
surge generator argument (fixed after the baseline; surge excluded from baseline metrics).

## Iteration 1 - 05:15-05:52 - accident traps (supervised phase: logic and thresholds)
- Failure cluster: accident traps, 53 false alarms in 100 trap scenarios, all from the trajectory rule
  ("vehicles overlap after an abrupt stop") on queues, red lights, perspective overlap, crowd crossing, camera shake;
  plus 0/40 on single-vehicle crashes (skid, divider, rollover, pedestrian hit): the rule needs two vehicles.
- Hypothesis: an impact stops a vehicle in about half a second; braking takes a second or more. The stable rule's
  "before" speed is an average that braking drags down, so ordinary braking passes it.
- Change (`DRISHTI_ACCIDENT_RULE=abrupt`, stable `v1` kept as default and fallback): peak = fastest 0.6 s stretch in
  the last 3 s; the vehicle must still be at >= 80% of that 0.6-1.2 s before the stop, moving >= 0.5 box-lengths/s,
  and the pair must have closed >= 0.15 box-diagonals in the second before contact; the hit is latched up to 8 s while
  the vehicles stay stopped. New single-vehicle hard-stop check (>= 1 box-length/s to standstill), raised by a person
  lying beside it or a box shape change.
- Synthetic, same 80 accident scenarios (variants 1-4): pass 37 -> 50, recall 18/40 -> 19/40, trap false alarms 21 -> 9.
- Real: see the promotion decision below (frozen test + validation run side by side on identical caches).

## Iteration 2 - 05:53-06:03 - loitering never fires (logic)
- Cluster: loitering 0/10. Two causes: the engine emits 0.55 confidence under a 0.60 gate, and it measures spread over
  the whole track history, so anyone who walked into view is ruled out.
- Change (switches): `DRISHTI_LOITER_CONF=0.65`, `DRISHTI_LOITER_WINDOW_S=30` (stable: 0.55 / whole history).
- Synthetic loitering (variants 1-5): 0/5 -> 5/5. Intrusion unchanged 5/5. No real loitering labels exist.

## Iteration 3 - 05:53-06:00 - overcrowding on flowing crowds (logic, false-alarm reduction)
- Cluster: festival procession 5/10 and train-arrival rush 4/10 raise "overcrowding" (25+ people in view) at
  Medium-Critical severity although the crowd is moving freely.
- Change: `DRISHTI_CROWD_FLOW_MAX=0.8` - overcrowding needs the median person speed below 0.8 body-heights/s
  (packed, not flowing). Stable: off.
- Synthetic (variants 1-5 of procession, train rush, overcrowding, crush, exit blocked, mob): see final evaluation.

## 06:03 refinement loop closed (deadline 06:00). No semi-/unsupervised phase was reached: see OVERNIGHT_REPORT.md.

## 06:05 accident classifier (pending task from the data brief) - trained, NOT promoted
- Logistic regression on SigLIP embeddings, 63 embedded clips (embedding job stopped at the 06:00 cut-off), frozen-test
  clips excluded from training. Out-of-fold frame AUC 0.928, but at the chosen threshold (0.90): validation UCF accidents
  0/16 caught, team videos 1.mp4 / 2.mp4 / 3.mp4 0/3 caught (leave-one-video-out), frozen test 1/7 caught, 0 false
  alarms on 19 negative clips. Written to `models/candidates/accident_clf.json`, not to `models/`, so the app does not
  load it. Results: `docs/results/accident_clf.json`.

## 06:35 promotion decision, iteration 1 (accident "abrupt" rule) - NOT promoted
REAL, identical caches, UCF-Crime clips (`docs/results/real_eval_acc_v1.json`, `real_eval_acc_abrupt.json`):
| | stable v1 | abrupt |
|---|---|---|
| frozen test: accidents detected | 4/7 | 3/7 |
| frozen test: early alarms | 2 | 2 |
| frozen test: false alarms (/ camera-hour) | 2 (8.4) | 1 (4.2) |
| validation: detected | 5/16 | 5/16 |
| validation: false alarms (/ camera-hour) | 4 (6.2) | 0 (0.0) |
The gate needs equal or better recall on the frozen test; abrupt loses one accident (4/7 -> 3/7), so the stable rule
stays the default. `DRISHTI_ACCIDENT_RULE=abrupt` remains available (it removes every validation false alarm and
halves frozen-test false alarms). Synthetic gains (traps 21 -> 9 false alarms) did not carry over to recall on real
footage, which is exactly what the guardrail is for.

## 07:17 done
Tests 48 pass, smoke test pass on the branch and on merged main. main merged (clean) and pushed with the branch. Nothing promoted; stable defaults unchanged. Report: OVERNIGHT_REPORT.md.
