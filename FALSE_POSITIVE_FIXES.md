# FALSE_POSITIVE_FIXES.md

Changes made specifically to cut false alarms, the scenarios they fixed, and what real footage said.
All are behind config switches; none is the default yet (see OVERNIGHT_REPORT.md for why).

| Change | Switch | Synthetic scenarios fixed (method A, variants 1-5 unless noted) | Real footage |
|---|---|---|---|
| Accident trajectory rule only fires on an impact stop: still >= 80% of peak speed 0.6-1.2 s before stopping, >= 0.5 box-lengths/s, and the two vehicles closing in just before contact | `DRISHTI_ACCIDENT_RULE=abrupt` | accident traps: false alarms 25 -> 12 on the paired set; red-light queue, perspective overlap, stop-and-go, crowd crossing, camera shake mostly clean (variants 1-4: 21 -> 9) | validation false alarms 4 -> 0, frozen test 2 -> 1; but frozen-test recall 4/7 -> 3/7, so not promoted |
| Overcrowding only for a packed crowd (median person speed below 0.8 body-heights/s), not a crowd flowing through | `DRISHTI_CROWD_FLOW_MAX=0.8` | festival procession, train-arrival rush: crowd-trap false alarms 6 -> 2 | no change on the frozen test or demo (no real clip has 25+ people moving) |

Fixes in the opposite direction (missed events), for completeness: loitering could never fire (confidence 0.55 under a
0.60 gate, and spread measured over the whole history including the walk in) - `DRISHTI_LOITER_CONF=0.65`,
`DRISHTI_LOITER_WINDOW_S=30`; single-vehicle crashes (skid, divider, rollover, pedestrian hit) had no rule at all - part
of the `abrupt` switch.
