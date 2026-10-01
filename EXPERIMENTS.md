# EXPERIMENTS.md

One row per training experiment: what changed, the number before, the number after, and
whether the change was kept. Every number comes from a file in `docs/results/` written by
the script named. "Before" is the model the app used at the time.

| # | Date | Task | Change | Before | After | Kept? | Result file |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-01 | accident | SigLIP-embedding logistic classifier, retrained with the real frozen test held out (63 embedded clips) | no classifier loaded | frozen test 1/7 caught, 0 false alarms on 19 clips; validation 0/16; team videos 0/3 (leave-one-out); frame AUC 0.928 | no (candidate in models/candidates) | docs/results/accident_clf.json |
| 2 | 2026-10-01 | accident | trajectory rule "abrupt" (impact stop + closing + single-vehicle) | real test 4/7, 2 FA; val 5/16, 4 FA; synthetic pairs 55/115 pass | real test 3/7, 1 FA; val 5/16, 0 FA; synthetic 67/115 pass, system scenarios 27 -> 19 | no (switch DRISHTI_ACCIDENT_RULE=abrupt) | real_eval_acc_v1.json, real_eval_acc_abrupt.json |
| 3 | 2026-10-01 | other | loitering confidence 0.65 and spread over the last 30 s | synthetic loitering 0/10 | 5/5 (variants 1-5); real: no loitering labels, demo unchanged | no (switches; recommended) | synthetic_suite_final_candidates.json |
| 4 | 2026-10-01 | crowd | overcrowding needs a packed (median speed < 0.8 body-heights/s) crowd | synthetic crowd traps 6 FA | 2 FA; real test crowd 3/4 both, FA 2 both; demo unchanged | no (switch DRISHTI_CROWD_FLOW_MAX=0.8) | real_eval_it23_test.json |
