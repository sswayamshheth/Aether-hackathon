# Pitch notes: ten questions judges are likely to ask

Numbers quoted here are from BENCH.md (generated from `docs/results/*.json`). If you rerun
the scripts, reread BENCH.md before the pitch: the tables update, this file does not.

### 1. Is this real-time?

On the development laptop (Intel i5-1230U, no GPU): the COCO detector runs at about 14
frames a second through OpenVINO (7 in PyTorch), shared between all cameras. We sample each
camera at about 10 fps and run detection on every second frame. With four live RTSP
cameras we measured about 4.9 fps per camera (3.7 when the machine was busy with other work). Demo
mode shows 10 fps because it replays cached detections. Say both numbers; do not present
the demo-mode figure as live performance.

### 2. How accurate is it?

We do not claim an accuracy figure: the evaluation set is small (8 accident clips, 11
crowd scenes, 6 baggage clips, 4 normal clips). What we measured end to end:

- Crowd anomaly: 10 of 11 UMN scenes detected, median delay 1.1 s, including all 4 scenes
  the model never trained on. Frame-level AUC on those held-out scenes is 0.99.
- Unattended baggage: 3 of 6 ABODA clips.
- Accident: 1 of 8 UCF-Crime clips, and 4 alarms that fired before the annotated onset.

Accident detection is our weakest part and we say so.

### 3. Why is accident detection so weak?

Both pretrained accident detectors we benched are single-frame models trained on clear
accident photos. On 320x240 CCTV footage they rarely fire at the moment of impact. The
unlicensed nano model looked better frame by frame (5 of 8 against 2 of 8) but was no
better once it ran inside the full pipeline (1 of 8). The honest fix is a model that looks
at motion over time, trained on CCTV accident video such as CADP. The Kaggle notebook for a
first fine-tune is in `training/kaggle/`.

### 4. What did you build, and what did you download?

Downloaded: the YOLO11n COCO detector, the ByteTrack tracker, one accident detector (MIT
licence). Built: the pipeline, the three engines, the crowd model (trained by us), the
false-alarm filter, severity scoring, cross-camera merging, operator feedback, evidence
clips, the dashboard, demo mode and the evaluation scripts. Details in
`docs/WHAT_WE_BUILT.md`.

### 5. You said "hybrid of the best repos". Which repos?

We benched five repos and one Hugging Face model on the same clips (BENCH.md). Two things
came out of that. First, none of the six repos we were pointed at has a licence file, so we
could not ship their code or weights; we re-implemented the ideas worth keeping and credit
them in CREDITS.md. Second, their results on shared clips were weaker than their READMEs
suggest: the count-based crowd rule flagged calm crowds and missed every dispersal, and the
abandoned-object logic fired on 1 of 6 clips. That is why the crowd model and the baggage
engine are our own.

### 6. How do you reduce false alarms?

Four checks between an engine and the operator: persistence over time, a confidence gate,
operator-drawn ignore zones, and agreement between cameras in the same area. On our 4
normal clips the engines produced 4 alarm groups and the filter let 1 through (a crowd
alarm in a supermarket). That is under two minutes of footage, so treat it as a direction,
not a rate. Every suppressed alarm is logged with the reason and shown on the Analytics
page.

### 7. How is severity decided? Is it a black box?

No. It is a 0-100 score built from named parts: incident type, model confidence, people
and vehicles involved, how long it has lasted, how many cameras see it, and for bags how
long the owner has been away. Each part is stored as a line the operator can read, with
its points. A learned severity model was on our list and we cut it; with this little data
it would have been less trustworthy than the rules.

### 8. What does multi-camera tracking mean here?

Cameras carry an area name. If two cameras in one area raise the same incident type within
30 seconds, they become one incident, the confidence is combined, and severity goes up.
We do not re-identify people or vehicles across cameras. In the demo the second junction
camera is the first clip mirrored and cropped, because we had no footage of one accident
from two angles. We say that on the slide.

### 9. What about privacy?

Everything runs locally; no frame leaves the machine by default. The optional vision-model
check blurs the head region of every detected person before sending three frames, and is
switched off unless a key is configured. There is no login on the dashboard yet, which is
a gap for any real deployment.

### 10. What would you do with another week?

1. Train a temporal accident model on CCTV accident video, and re-measure on a larger set.
2. Fine-tune a luggage detector (notebook ready) so the baggage logic gets the detections
   it needs.
3. Collect real crowd footage: the crowd model has only seen staged scenes.
4. Run on a GPU or an edge accelerator and measure four to eight cameras properly.
5. Add authentication and an audit trail for operator actions.
