"""Supervised accident classifier: is this frame an accident scene?

    backend\\.venv\\Scripts\\python training\\train_accident_clf.py

Data
  positives  frames from annotated accident windows: the 23 UCF-Crime RoadAccidents test
             clips and our own labelled videos in data/custom (labels in LABELS below)
  negatives  frames more than 2 s before an accident, and every frame of the normal clips
             and of the other UCF-Crime classes (fire, fights, robbery, ...)
  dropped    frames in the aftermath (after the labelled window) and 2 s before onset,
             where "accident or not" is unclear
Features   SigLIP image embedding (the same scene model the live system already runs),
           frames sampled at 1 fps
Model      L2-regularised logistic regression, weights saved as JSON (no pickle)
Evaluation grouped by clip, so a clip is never in training and test at once:
           frame AUC, and event level: an accident counts as caught when 2 consecutive
           frames (1 s apart) pass the threshold between 1 s before onset and the end of
           the window; any such run on a normal clip is a false alarm. Each of our own
           videos is also reported alone (leave-one-video-out).
Writes     models/accident_clf.json, docs/results/accident_clf.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "models")

from app import config  # noqa: E402

EMB = ROOT / "data" / "cache" / "embeddings"
EMB.mkdir(parents=True, exist_ok=True)
CUSTOM = ROOT / "data" / "custom"
WINDOW_S = 10.0  # an accident is labelled from onset to onset + 10 s
# our own videos: accident onset in seconds, as given by the team (0:04, 0:05, 0:22)
LABELS = {"1.mp4": 4.0, "2.mp4": 5.0, "3.mp4": 22.0}
HOLDOUT = {"Fighting033_x264.mp4", "Arson010_x264.mp4"}  # demo clips, never trained on


def clip_list() -> list[dict]:
    clips = [c for c in json.loads((ROOT / "data" / "cache" / "features" / "clips.json").read_text())
             if c["clip"] not in HOLDOUT]
    for name, onset in LABELS.items():
        p = CUSTOM / name
        if not p.exists():
            continue
        cap = cv2.VideoCapture(str(p))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        cap.release()
        clips.append({"clip": f"custom_{name}", "path": str(p), "class": "CustomAccident",
                      "windows": [(onset, onset + WINDOW_S)], "start_s": 0.0, "end_s": dur, "fps": fps})
    return clips


def label(c: dict, t: float) -> int | None:
    if c["class"] not in {"RoadAccidents", "CustomAccident"}:
        return 0
    for a, b in c["windows"]:
        end = min(b, a + WINDOW_S) if c["class"] == "RoadAccidents" else b
        if a <= t <= end:
            return 1
        if a - 2 <= t < a or end < t:
            return None
    return 0


def embed_all(clips: list[dict]) -> None:
    import torch
    from transformers import AutoModel, AutoProcessor

    from app.aux_models import device

    todo = [c for c in clips if not (EMB / f"{Path(c['clip']).stem}.npz").exists()]
    if not todo:
        return
    dev = device()
    proc = AutoProcessor.from_pretrained(str(config.MODELS / "siglip"))
    model = AutoModel.from_pretrained(str(config.MODELS / "siglip")).eval().to(dev)
    for c in todo:
        cap = cv2.VideoCapture(c["path"])
        ts, vecs = [], []
        t = c["start_s"]
        t0 = time.time()
        while t <= c["end_s"]:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, img = cap.read()
            if not ok:
                break
            with torch.no_grad():
                px = proc(images=cv2.cvtColor(img, cv2.COLOR_BGR2RGB), return_tensors="pt")["pixel_values"].to(dev)
                e = model.get_image_features(pixel_values=px)
                e = (e / e.norm(dim=-1, keepdim=True))[0].float().cpu().numpy()
            ts.append(t)
            vecs.append(e)
            t += 1.0
        cap.release()
        np.savez(EMB / f"{Path(c['clip']).stem}.npz", t=np.array(ts), e=np.array(vecs, dtype=np.float32))
        print(f"embedded {c['clip']}: {len(ts)} frames {time.time() - t0:.0f}s", flush=True)


def auc(y, s) -> float | None:
    y, s = np.asarray(y), np.asarray(s)
    if len(set(y)) < 2:
        return None
    order = np.argsort(s)
    r = np.empty(len(s))
    r[order] = np.arange(1, len(s) + 1)
    pos = y == 1
    return float((r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def events(c: dict, t: np.ndarray, p: np.ndarray, thr: float) -> dict:
    """Runs of 2 consecutive frames at or above thr, split into hit / early / false alarm."""
    starts = [t[i] for i in range(1, len(p)) if p[i] >= thr and p[i - 1] >= thr and (i < 2 or p[i - 2] < thr)]
    if c["class"] in {"RoadAccidents", "CustomAccident"}:
        a, b = c["windows"][0]
        end = min(b, a + WINDOW_S)
        hits = [s for s in starts if a - 1 <= s <= end]
        early = [s for s in starts if s < a - 1]
        return {"caught": bool(hits), "delay_s": round(float(hits[0] - a), 1) if hits else None, "early": len(early)}
    return {"false_alarms": len(starts)}


def main() -> None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    clips = clip_list()
    embed_all(clips)
    X, y, groups, meta = [], [], [], []
    for c in clips:
        d = np.load(EMB / f"{Path(c['clip']).stem}.npz")
        for t, e in zip(d["t"], d["e"]):
            lab = label(c, float(t))
            if lab is None:
                continue
            X.append(e)
            y.append(lab)
            groups.append(c["clip"])
    X, y, groups = np.array(X), np.array(y), np.array(groups)
    print(f"{len(y)} frames, {int(y.sum())} accident frames, {len(set(groups))} clips", flush=True)

    def fit(Xa, ya):
        return LogisticRegression(C=0.5, class_weight="balanced", max_iter=3000).fit(Xa, ya)

    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        oof[te] = fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    # leave-one-video-out for our own videos (each trained on everything else)
    custom_p = {}
    for c in clips:
        if c["class"] != "CustomAccident":
            continue
        m = fit(X[groups != c["clip"]], y[groups != c["clip"]])
        d = np.load(EMB / f"{Path(c['clip']).stem}.npz")
        custom_p[c["clip"]] = (d["t"], m.predict_proba(d["e"])[:, 1])

    # score every clip over its whole segment with out-of-fold probabilities
    fold_of = {}
    for k, (tr, te) in enumerate(GroupKFold(n_splits=5).split(X, y, groups)):
        for g in set(groups[te]):
            fold_of[g] = k
    models = {}
    for k, (tr, te) in enumerate(GroupKFold(n_splits=5).split(X, y, groups)):
        models[k] = fit(X[tr], y[tr])

    def clip_probs(c):
        if c["clip"] in custom_p:
            return custom_p[c["clip"]]
        d = np.load(EMB / f"{Path(c['clip']).stem}.npz")
        return d["t"], models[fold_of[c["clip"]]].predict_proba(d["e"])[:, 1]

    best = None
    for thr in np.arange(0.5, 0.96, 0.05):
        rows = [events(c, *clip_probs(c), thr) for c in clips if c["clip"] in fold_of or c["clip"] in custom_p]
        caught = sum(r.get("caught", False) for r in rows)
        fa = sum(r.get("false_alarms", 0) + r.get("early", 0) for r in rows)
        score = caught - 0.5 * fa
        if best is None or score > best[0]:
            best = (score, round(float(thr), 2))
    thr = best[1]
    per_clip = []
    for c in clips:
        if c["class"] in {"RoadAccidents", "CustomAccident", "Normal"}:
            per_clip.append({"clip": c["clip"], "class": c["class"], **events(c, *clip_probs(c), thr)})
    acc = [r for r in per_clip if r["class"] == "RoadAccidents"]
    cus = [r for r in per_clip if r["class"] == "CustomAccident"]
    nor = [r for r in per_clip if r["class"] == "Normal"]
    other_fa = sum(events(c, *clip_probs(c), thr).get("false_alarms", 0) for c in clips
                   if c["class"] not in {"RoadAccidents", "CustomAccident", "Normal"})
    final = fit(X, y)
    res = {
        "model": "logistic regression on SigLIP image embeddings (768-d), frames at 1 fps",
        "labels": {"window_s": WINDOW_S, "custom_onsets_s": LABELS},
        "frames": int(len(y)), "accident_frames": int(y.sum()), "clips": len(set(groups)),
        "frame_auc_out_of_fold": round(auc(y, oof), 4), "threshold": thr,
        "ucf_accidents": {"clips": len(acc), "caught": sum(r["caught"] for r in acc),
                          "early_alarms": sum(r["early"] for r in acc)},
        "own_videos_leave_one_out": cus,
        "normal_clips": {"clips": len(nor), "clips_with_false_alarm": sum(1 for r in nor if r["false_alarms"]),
                         "false_alarms": sum(r["false_alarms"] for r in nor)},
        "other_class_false_alarms": other_fa,
        "per_clip": per_clip,
    }
    (config.RESULTS / "accident_clf.json").write_text(json.dumps(res, indent=1))
    (config.MODELS / "accident_clf.json").write_text(json.dumps(
        {"coef": final.coef_[0].round(6).tolist(), "intercept": round(float(final.intercept_[0]), 6),
         "threshold": thr, "embedding": "google/siglip-base-patch16-224 image features, L2-normalised"}))
    print(json.dumps({k: v for k, v in res.items() if k != "per_clip"}, indent=1))


if __name__ == "__main__":
    main()
