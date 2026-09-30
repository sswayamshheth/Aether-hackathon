"""Train the ML verifier for each incident type, on top of the rule engines.

    backend\\.venv\\Scripts\\python training\\train_verifiers.py

1. Replays every clip cached by extract_features.py through the real pipeline (same
   engines, same grouping as live), with confirmation switched off, and records the feature
   summary of every candidate group each time the rules would have let it through.
2. Labels each snapshot from the UCF-Crime annotations:
     positive  the clip's class belongs to the incident type and the snapshot falls inside
               an annotated window (2 s before to 5 s after)
     negative  normal clips, clips of unrelated classes, and snapshots more than 10 s
               outside the windows of related clips
     dropped   snapshots in the 2-10 s margin around a window (the label is unclear there)
3. Per type: standardised logistic regression, evaluated with grouped 5-fold cross
   validation (a clip is never in train and test at once). The decision threshold is picked
   on the out-of-fold predictions. The rule gate is scored on the same events, so the two
   can be compared directly.
4. Writes models/verifiers.json (weights as plain JSON) and docs/results/verifiers.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "training"))
os.chdir(ROOT / "models")

from app import config  # noqa: E402
from app.db import Store  # noqa: E402
from app.intel import verifier as vmod  # noqa: E402
from app.runtime import Pipeline, Runtime  # noqa: E402
from extract_features import OUT, frames  # noqa: E402

POSITIVE = {
    "accident": {"RoadAccidents"},
    "fire": {"Arson", "Explosion"},
    "violence": {"Fighting", "Assault", "Abuse", "Robbery", "Shooting"},
    "weapon": {"Shooting", "Robbery"},
    "hazard": {"Vandalism"},
}
MIN_EVENTS = 8  # a type needs at least this many positive and negative events to be trained
# kept out of training entirely: these two become demo cameras 5 and 6, so the demo shows
# the verifier on footage it has never seen
HOLDOUT = {"Fighting033_x264.mp4", "Arson010_x264.mp4"}


def collect() -> list[dict]:
    clips = json.loads((OUT / "clips.json").read_text())
    rows: list[dict] = []
    saved_gate = dict(config.GATE)
    for k in config.GATE:
        config.GATE[k] = 9.0  # nothing confirms, so every group keeps being observed
    for meta in clips:
        p = OUT / f"{Path(meta['clip']).stem}.json"
        if not p.exists() or meta["clip"] in HOLDOUT:
            continue
        data = json.loads(p.read_text())
        if "tracks" not in data["passes"]:
            continue
        store = Store(":memory:")
        rt = Runtime(store, live=False)
        rt.filter.verifier = vmod.Verifier(Path("__none__"))

        def observe(key, group, summary, meta=meta):
            rows.append({"clip": meta["clip"], "class": meta["class"], "type": key[1], "key": key[2],
                         "group": f"{meta['clip']}|{key[2]}|{group.first_ts:.1f}", "t": group.last_ts,
                         "windows": meta["windows"], "features": summary})

        rt.filter.observer = observe
        cam = {"id": "train", "name": "train", "source": meta["path"], "kind": "file", "area": "train",
               "profile": "all"}
        pipe = Pipeline(cam, rt, fps=config.TARGET_FPS, cache=data["frames"])
        for idx, ts, img in frames(meta):
            pipe.process(img, ts, idx)
        print(f"{meta['clip']}: {sum(1 for r in rows if r['clip'] == meta['clip'])} snapshots", flush=True)
    config.GATE.update(saved_gate)
    return rows


def label(r: dict) -> int | None:
    pos_classes = POSITIVE.get(r["type"], set())
    if r["type"] == "hazard" and not r["key"].endswith("vandalism"):
        pos_classes = set()
    if r["class"] not in pos_classes:
        return 0
    t = r["t"]
    if any(a - 2 <= t <= b + 5 for a, b in r["windows"]):
        return 1
    if all(t < a - 10 or t > b + 10 for a, b in r["windows"]):
        return 0
    return None


def auc(y: np.ndarray, s: np.ndarray) -> float | None:
    if len(set(y)) < 2:
        return None
    order = np.argsort(s)
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    for v in np.unique(s):
        m = s == v
        ranks[m] = ranks[m].mean()
    pos = y == 1
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def group_metrics(groups: np.ndarray, y: np.ndarray, decide: np.ndarray) -> dict:
    """Event level: a group counts as raised if any of its snapshots passes."""
    gy, gd = {}, {}
    for g, yy, d in zip(groups, y, decide):
        gy[g] = max(gy.get(g, 0), yy)
        gd[g] = gd.get(g, False) or bool(d)
    tp = sum(1 for g in gy if gy[g] and gd[g])
    fp = sum(1 for g in gy if not gy[g] and gd[g])
    fn = sum(1 for g in gy if gy[g] and not gd[g])
    return {"events": len(gy), "positive_events": sum(gy.values()), "raised": tp + fp, "true_alarms": tp,
            "false_alarms": fp, "missed": fn, "precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None}


def train_type(typ: str, rows: list[dict]) -> dict | None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    rows = [r for r in rows if r["type"] == typ and r["y"] is not None]
    if not rows:
        return None
    names = sorted({k for r in rows for k in r["features"]})
    X = np.array([[r["features"].get(k, np.nan) for k in names] for r in rows], dtype=float)
    col_mean = np.nanmean(X, axis=0)
    X = np.where(np.isnan(X), col_mean, X)
    y = np.array([r["y"] for r in rows])
    groups = np.array([r["group"] for r in rows])
    clips = np.array([r["clip"] for r in rows])
    n_pos_ev = len({g for g, yy in zip(groups, y) if yy})
    n_neg_ev = len({g for g, yy in zip(groups, y) if not yy})
    info = {"snapshots": len(rows), "positive_events": n_pos_ev, "negative_events": n_neg_ev,
            "clips": len(set(clips)), "features": len(names)}
    if n_pos_ev < MIN_EVENTS or n_neg_ev < MIN_EVENTS:
        info["trained"] = False
        info["why"] = f"needs {MIN_EVENTS}+ positive and negative events"
        return info

    def fit(Xa, ya):
        mu, sd = Xa.mean(0), Xa.std(0) + 1e-6
        m = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000).fit((Xa - mu) / sd, ya)
        return m, mu, sd

    oof = np.zeros(len(y))
    folds = min(5, len(set(clips)))
    for tr, te in GroupKFold(n_splits=folds).split(X, y, clips):
        if len(set(y[tr])) < 2:
            oof[te] = y[tr].mean()
            continue
        m, mu, sd = fit(X[tr], y[tr])
        oof[te] = m.predict_proba((X[te] - mu) / sd)[:, 1]

    best = (0.5, -1.0)
    for thr in np.arange(0.3, 0.96, 0.05):  # threshold with the best event-level F1, out of fold
        gm = group_metrics(groups, y, oof >= thr)
        p, r = gm["precision"] or 0, gm["recall"] or 0
        f1 = 2 * p * r / (p + r) if p + r else 0
        if f1 > best[1]:
            best = (round(float(thr), 2), f1)
    thr = best[0]
    conf_col = [i for i, n in enumerate(names) if n.endswith("__mean") and n.split("__")[0] in
                {"model_conf", "fire_conf", "weapon_conf", "violence_p", "fallen_conf", "crowd_p", "scene_prob"}]
    rule = None
    if conf_col:  # the rule gate on the same events: mean detector confidence >= GATE
        rule = group_metrics(groups, y, X[:, conf_col[0]] >= config.GATE[typ])
        rule["gate"] = config.GATE[typ]
    m, mu, sd = fit(X, y)
    info.update(trained=True, threshold=thr, snapshot_auc_out_of_fold=round(auc(y, oof), 3) if auc(y, oof) else None,
                verifier_out_of_fold=group_metrics(groups, y, oof >= thr), rule_gate=rule, folds=folds)
    top = sorted(zip(names, m.coef_[0]), key=lambda t: -abs(t[1]))[:6]
    info["strongest_features"] = [{"feature": vmod.readable(n), "weight": round(float(w), 3)} for n, w in top]
    info["_model"] = {"features": names, "mean": mu.round(6).tolist(), "std": sd.round(6).tolist(),
                      "coef": m.coef_[0].round(6).tolist(), "intercept": round(float(m.intercept_[0]), 6),
                      "threshold": thr}
    return info


def main() -> None:
    rows = collect()
    for r in rows:
        r["y"] = label(r)
    (ROOT / "data" / "cache" / "verifier_rows.json").write_text(json.dumps(rows))
    report, models = {}, {}
    for typ in sorted({r["type"] for r in rows}):
        info = train_type(typ, rows)
        if info is None:
            continue
        if info.get("trained"):
            models[typ] = info.pop("_model")
        report[typ] = info
        print(typ, json.dumps({k: v for k, v in info.items() if k != "strongest_features"}), flush=True)
    clips = json.loads((OUT / "clips.json").read_text())
    per_class: dict[str, int] = {}
    for c in clips:
        per_class[c["class"]] = per_class.get(c["class"], 0) + 1
    out = {"method": "per-type logistic regression on group features; grouped 5-fold CV by clip",
           "held_out_for_demo": sorted(HOLDOUT),
           "dataset": "UCF-Crime annotated test videos (plus normal videos), 45 s around each incident",
           "clips_by_class": per_class, "positive_classes": {k: sorted(v) for k, v in POSITIVE.items()},
           "types": report}
    (config.RESULTS / "verifiers.json").write_text(json.dumps(out, indent=1))
    (config.MODELS / "verifiers.json").write_text(json.dumps({"types": models}, indent=1))
    print(f"trained verifiers: {sorted(models)}")


if __name__ == "__main__":
    main()
