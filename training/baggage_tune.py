"""Phase C, baggage: tune the abandonment logic against event timestamps.

    backend\\.venv\\Scripts\\python training\\baggage_tune.py tracks   (detector pass, cached)
    backend\\.venv\\Scripts\\python training\\baggage_tune.py tune

The bag detector itself is not fine-tuned here: that needs the Roboflow luggage sets
(blocked, SIGNUP_NEEDED.md) and a GPU. What is tuned is the explicit owner/abandonment
logic in backend/app/engines/baggage.py, by grid search:
  NEAR_K            how close (in person heights) counts as "owner near"
  unattended_s      owner away this long -> candidate
  MIN_SIGHTINGS     detections a bag needs before it can raise anything
  MISSING_GRACE_S   how long a bag survives missed detections
  gate              confidence gate in the false-alarm filter

Data
  AVSS 2007 (3 videos, UAM ground truth): AbandonedObject start frame = when the 30 s
  rule is met. A hit is an alarm between 5 s before that and the end of the event.
  ABODA (6 bench videos): each contains one abandonment, but no timestamps; scored as
  flagged or not. ABODA does not follow the 30 s rule, so it is scored with its own
  shorter unattended time (the best of 5 / 10 / 15 s on the same grid).
  Normal footage: the UCF-Crime normal clips already tracked by extract_features.py,
  for false alarms per camera-hour.
Objective (on train+val videos only): hits - 0.5 * false alarms, then lowest delay.
The frozen test split is scored once with the chosen setting.
Writes docs/results/baggage_logic.json, a row in EXPERIMENTS.md
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "models")

from app import config  # noqa: E402
from app.engines import baggage as bag_mod  # noqa: E402
from app.schema import Frame, Track  # noqa: E402

TRACKS = ROOT / "data" / "cache" / "bag_tracks"
TRACKS.mkdir(parents=True, exist_ok=True)
LABELS = ROOT / "data" / "labels" / "baggage_events.csv"
DEFAULTS = {"NEAR_K": bag_mod.NEAR_K, "unattended_s": config.BAG_UNATTENDED_S,
            "MIN_SIGHTINGS": bag_mod.MIN_SIGHTINGS, "MISSING_GRACE_S": bag_mod.MISSING_GRACE_S,
            "gate": config.GATE["baggage"]}
GRID = {"NEAR_K": [0.6, 0.9, 1.2], "unattended_s": [10.0, 20.0, 30.0], "MIN_SIGHTINGS": [3, 6, 10],
        "MISSING_GRACE_S": [4.0, 8.0, 15.0], "gate": [0.12, 0.18, 0.25]}
ABODA_UNATTENDED = [5.0, 10.0, 15.0]


def key(v: str) -> Path:
    return TRACKS / (hashlib.sha1(v.encode("utf-8")).hexdigest()[:16] + ".json")


def videos() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with LABELS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = out.setdefault(r["video_path"], {"split": r["split"], "events": [], "source": r["source"]})
            if r["event_type"] in {"abandoned", "abandoned_untimed"}:
                m["events"].append((float(r["start_s"]), float(r["end_s"]), r["event_type"]))
    return out


def extract_tracks() -> None:
    import cv2

    from app.detector import Tracker, get_detector
    from app.runtime import BAG_IDS

    det = get_detector()
    for v in videos():
        if key(v).exists():
            continue
        cap = cv2.VideoCapture(str(ROOT / v))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, round(fps / config.TARGET_FPS))
        tracker, i, n, recs, t0 = Tracker(config.TARGET_FPS / config.DETECT_EVERY), -1, 0, [], time.time()
        while cap.grab():
            i += 1
            if i % step:
                continue
            n += 1
            if n % config.DETECT_EVERY:
                continue
            ok, img = cap.retrieve()
            if not ok:
                break
            boxes = det.detect(img)
            is_bag = np.isin(boxes.cls.astype(int), BAG_IDS)
            moving = tracker.update(boxes[~is_bag], img)
            bags = [[0, config.COCO[int(c)], *[round(float(x), 1) for x in b], round(float(p), 3)]
                    for b, c, p in zip(boxes.xyxy[is_bag], boxes.cls[is_bag], boxes.conf[is_bag])]
            recs.append([round(i / fps, 2), [[t.id, t.cls, *[round(x, 1) for x in t.box], round(t.conf, 3)]
                                             for t in moving if t.cls == "person"] + bags])
        cap.release()
        key(v).write_text(json.dumps({"video": v, "size": [int(img.shape[1]), int(img.shape[0])] if recs else [0, 0],
                                      "frames": recs}))
        print(f"{v}: {len(recs)} detector frames {time.time() - t0:.0f}s", flush=True)


def normal_tracks() -> list[dict]:
    """UCF-Crime normal clips already tracked for the verifier work (extract_features.py)."""
    out = []
    for p in (ROOT / "data" / "cache" / "features").glob("Normal_Videos_*.json"):
        d = json.loads(p.read_text())
        recs = []
        for idx, r in sorted(d["frames"].items(), key=lambda kv: int(kv[0])):
            if r.get("fresh"):
                recs.append([int(idx) / d["meta"]["fps"], r["tracks"]])
        out.append({"video": d["meta"]["clip"], "size": [320, 240], "frames": recs})
    return out


def run(data: dict, p: dict) -> list[tuple[float, str]]:
    """Replay the baggage engine + the filter's gate/persistence; returns (time, subtype) of raised events."""
    bag_mod.NEAR_K, bag_mod.MIN_SIGHTINGS, bag_mod.MISSING_GRACE_S = p["NEAR_K"], p["MIN_SIGHTINGS"], p["MISSING_GRACE_S"]
    config.BAG_UNATTENDED_S, config.BAG_ABANDONED_S = p["unattended_s"], p["unattended_s"] + 20
    eng = bag_mod.BaggageEngine("tune")
    img = np.zeros((data["size"][1] or 240, data["size"][0] or 320, 3), np.uint8)
    raised, seen = [], set()
    for ts, tr in data["frames"]:
        tracks = [Track(t[0], t[1], tuple(t[2:6]), t[6]) for t in tr]
        for c in eng.process(Frame("tune", ts, img, tracks, True, None, [])):
            if c.key in seen or c.conf < p["gate"]:
                continue
            seen.add(c.key)
            raised.append((ts, c.subtype))
    return raised


def score(vmeta: dict, raised: list[tuple[float, str]]) -> dict:
    ev = vmeta["events"]
    if not ev:
        return {"false_alarms": len(raised)}
    if ev[0][2] == "abandoned_untimed":
        return {"flagged": bool(raised), "first_s": raised[0][0] if raised else None}
    a, b, _ = ev[0]
    hits = [t for t, _ in raised if a - 5 <= t <= b]
    return {"hit": bool(hits), "delay_s": round(hits[0] - a, 1) if hits else None,
            "false_alarms": sum(1 for t, _ in raised if not (a - 5 <= t <= b))}


def evaluate(p: dict, vids: dict, cache: dict, normals: list, split_filter, aboda_s: float | None = None) -> dict:
    hits = fa = flagged = n_timed = n_untimed = 0
    delays = []
    for v, meta in vids.items():
        if not split_filter(meta["split"]) or v not in cache:
            continue
        pp = dict(p)
        if meta["source"] == "ABODA" and aboda_s:
            pp["unattended_s"] = aboda_s
        s = score(meta, run(cache[v], pp))
        if "hit" in s:
            n_timed += 1
            hits += s["hit"]
            fa += s["false_alarms"]
            if s["delay_s"] is not None:
                delays.append(s["delay_s"])
        elif "flagged" in s:
            n_untimed += 1
            flagged += s["flagged"]
    nfa, secs = 0, 0.0
    for d in normals:
        r = run(d, p)
        nfa += len(r)
        secs += (d["frames"][-1][0] - d["frames"][0][0]) if d["frames"] else 0
    return {"timed_videos": n_timed, "hits": hits, "median_delay_s": sorted(delays)[len(delays) // 2] if delays else None,
            "false_alarms_on_event_videos": fa, "untimed_videos": n_untimed, "flagged": flagged,
            "normal_videos": len(normals), "normal_false_alarms": nfa,
            "normal_false_alarms_per_camera_hour": round(nfa / (secs / 3600), 1) if secs else None}


def tune() -> None:
    vids = videos()
    cache = {v: json.loads(key(v).read_text()) for v in vids if key(v).exists()}
    normals = normal_tracks()
    tv = lambda s: s in {"train", "val"}  # noqa: E731
    results = []
    for combo in itertools.product(*GRID.values()):
        p = dict(zip(GRID, combo))
        r = evaluate(p, vids, cache, normals, tv)
        obj = r["hits"] + r["flagged"] - 0.5 * (r["false_alarms_on_event_videos"] + r["normal_false_alarms"])
        results.append((obj, -(r["median_delay_s"] or 999), p, r))
    results.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best_p = results[0][2]
    aboda_best = max(ABODA_UNATTENDED, key=lambda s: evaluate(best_p, vids, cache, [], tv, aboda_s=s)["flagged"])
    test_default = evaluate(DEFAULTS, vids, cache, normals, lambda s: s == "test")
    test_best = evaluate(best_p, vids, cache, normals, lambda s: s == "test", aboda_s=aboda_best)
    tv_default = evaluate(DEFAULTS, vids, cache, normals, tv)
    res = {"created": datetime.now().isoformat(timespec="seconds"),
           "data": {"timed": "AVSS 2007 via UAM ground truth", "untimed": "ABODA", "normal": "UCF-Crime normal clips",
                    "videos_by_split": {s: sum(1 for m in vids.values() if m["split"] == s) for s in ("train", "val", "test")}},
           "grid": GRID, "combinations": len(results), "default_params": DEFAULTS, "best_params": best_p,
           "aboda_unattended_s": aboda_best,
           "train_val": {"default": tv_default, "best": results[0][3]},
           "test": {"default": test_default, "best": test_best},
           "note": "3 timed videos and 6 untimed ones is far too few to trust a tuned value; see EXPERIMENTS.md"}
    (ROOT / "docs" / "results" / "baggage_logic.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    extract_tracks() if sys.argv[1] == "tracks" else tune()
