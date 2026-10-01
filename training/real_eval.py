"""Real-footage evaluation used as the judge for every overnight change.

    backend\\.venv\\Scripts\\python training\\real_eval.py [--split val|test|demo|all] [--tag name]
    backend\\.venv\\Scripts\\python training\\real_eval.py --build-tracks   # once: detector + tracker caches

Replays cached detector / tracker / model outputs through the real pipeline, so a logic or
threshold change is re-scored in minutes without re-running YOLO. Splits are BY VIDEO and
fixed in this file (DECISIONS.md #20):

  frozen test (never tuned on)
    accident  UCF-Crime RoadAccidents clips whose index in sorted order is 2 mod 3, plus the
              same third of the Normal and other-class clips as negatives
    crowd     UMN scenes 1, 4, 7, 9 (also held out of crowd-model training)
    baggage   AVSS 2007 easy / medium / hard (UAM ground truth; new tonight, untouched)
  validation (tuning allowed)
    the other two thirds of the UCF-Crime clips, UMN scenes 0 2 3 5 6 8 10, ABODA 1 2 3 4 9 10
  demo_eval
    the four demo cameras (cached detections of the demo clips)

Metrics per family: event recall, median delay, precision, F1, and false alarms per
camera-hour on footage with no event of that family. Writes docs/results/real_eval[_tag].json.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "training"))
os.chdir(ROOT / "models")

import logging  # noqa: E402

logging.disable(logging.WARNING)

from app import config  # noqa: E402
from app.db import Store  # noqa: E402
from app.runtime import Pipeline, Runtime  # noqa: E402

FEAT = ROOT / "data" / "cache" / "features"
TRACKS = ROOT / "data" / "cache" / "tracks"
TRACKS.mkdir(parents=True, exist_ok=True)
BENCH = ROOT / "data" / "bench"
AVSS = ROOT / "data" / "raw" / "uam_aod" / "datasets" / "AVSS2007"
UMN_TEST = {1, 4, 7, 9}
EARLY_MARGIN = 1.0


# ------------------------------------------------------------------ clip lists
def ucf_clips() -> list[dict]:
    clips = json.loads((FEAT / "clips.json").read_text())
    by_cls: dict[str, list] = {}
    for c in sorted(clips, key=lambda c: c["clip"]):
        by_cls.setdefault(c["class"], []).append(c)
    out = []
    for cls, cs in by_cls.items():
        for i, c in enumerate(cs):
            fam = {"RoadAccidents": "accident"}.get(cls)
            out.append({"name": c["clip"], "kind": "ucf", "meta": c, "split": "test" if i % 3 == 2 else "val",
                        "family": fam, "events": [(a, b) for a, b in c["windows"]] if fam else [],
                        "start": c["start_s"], "end": c["end_s"], "path": c["path"]})
    return out


def umn_clips() -> list[dict]:
    lab = json.loads((BENCH / "crowd" / "umn_labels.json").read_text())
    fps = lab["fps"]
    return [{"name": f"umn_scene{si}", "kind": "video", "path": str(BENCH / "crowd" / "umn_all.avi"),
             "start_frame": s["start"], "end_frame": s["end"], "family": "crowd", "mask_rows": 24,
             "events": [(s["onset"] / fps, s["end"] / fps + 3)], "split": "test" if si in UMN_TEST else "val",
             "profile": "public"} for si, s in enumerate(lab["scenes"])]


def aboda_clips() -> list[dict]:
    return [{"name": p.stem, "kind": "video", "path": str(p), "family": "baggage", "events": None,
             "split": "val", "profile": "public"} for p in sorted((BENCH / "baggage").glob("aboda_*.mp4"))]


def avss_clips() -> list[dict]:
    out = []
    for level in ("EASY", "MEDIUM", "HARD"):
        txt = (AVSS / f"AVSSS07_{level}.txt").read_text()
        spans = dict((name, span) for span, name in re.findall(r'framespan="([^"]+)" id="\d+" name="(\w+)"', txt))
        put = int(spans["PutObject"].split(":")[0])
        ab = int(spans["AbandonedObject"].split(":")[0])
        fps = 25.0
        out.append({"name": f"avss2007_{level.lower()}", "kind": "video", "path": str(AVSS / f"AVSSS07_{level}.mpg"),
                    "family": "baggage", "events": [(put / fps, ab / fps + 20)], "split": "test",
                    "profile": "public", "start_frame": max(0, put - 20 * 25), "end_frame": ab + 40 * 25,
                    "put_s": put / fps,
                    "abandoned_s": ab / fps})
    return out


def demo_clips() -> list[dict]:
    exp = {"cam1": "accident", "cam2": "accident", "cam3": "baggage", "cam4": "crowd"}
    return [{"name": f"demo_{c}", "kind": "demo", "cam": c, "path": str(config.DEMO / "clips" / f"{c}.mp4"),
             "family": f, "events": None, "split": "demo",
             "profile": "traffic" if f == "accident" else "public"} for c, f in exp.items()]


# ------------------------------------------------------------------ frames
def video_frames(path: str, start_frame: int = 0, end_frame: int | None = None, mask_rows: int = 0):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps / config.TARGET_FPS))
    if start_frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    idx = start_frame - 1
    while True:
        ok, img = cap.read()
        if not ok:
            break
        idx += 1
        if end_frame is not None and idx > end_frame:
            break
        if idx % step:
            continue
        if mask_rows:
            img[:mask_rows] = 0
        yield idx, idx / fps, img
    cap.release()


def build_tracks(clips: list[dict]) -> None:
    """Detector + tracker only (no auxiliary models), cached per clip."""
    from app import runtime

    runtime.get_models = lambda: {}
    for c in clips:
        out = TRACKS / f"{c['name']}.json"
        if out.exists():
            continue
        t0 = time.time()
        store = Store(":memory:")
        rt = Runtime(store, live=False)
        cam = {"id": "x", "name": "x", "source": c["path"], "kind": "file", "area": "x", "profile": c["profile"]}
        pipe = Pipeline(cam, rt, fps=config.TARGET_FPS, record=True)
        n = 0
        for idx, ts, img in video_frames(c["path"], c.get("start_frame", 0), c.get("end_frame"), c.get("mask_rows", 0)):
            pipe.process(img, ts, idx)
            n += 1
        out.write_text(json.dumps(pipe.record, separators=(",", ":")))
        print(f"tracks {c['name']}: {n} frames {time.time() - t0:.0f}s", flush=True)


# ------------------------------------------------------------------ replay
def replay(c: dict) -> dict:
    store = Store(":memory:")
    rt = Runtime(store, live=False)
    if c["kind"] == "ucf":
        from extract_features import frames

        cache = json.loads((FEAT / f"{Path(c['name']).stem}.json").read_text())["frames"]
        it = frames(c["meta"])
        profile = "all"
    elif c["kind"] == "demo":
        from app.runtime import load_cache

        cache = load_cache(c["cam"])
        it = video_frames(c["path"])
        profile = c["profile"]
    else:
        p = TRACKS / f"{c['name']}.json"
        if not p.exists():
            return {"skipped": "no track cache"}
        cache = json.loads(p.read_text())
        it = video_frames(c["path"], c.get("start_frame", 0), c.get("end_frame"), c.get("mask_rows", 0))
        profile = c["profile"]
    cam = {"id": "eval", "name": "eval", "source": c["path"], "kind": "file", "area": "eval", "profile": profile}
    pipe = Pipeline(cam, rt, fps=config.TARGET_FPS, cache=cache)
    first = last = None
    for idx, ts, img in it:
        first = ts if first is None else first
        last = ts
        pipe.process(img, ts, idx)
    rt.filter.flush("eval", last or 0)
    incs = []
    for h in rt.history:
        row = store.incident(h["id"]) or {}
        incs.append({"type": h["type"], "subtype": h["subtype"], "ts": round(h["ts"], 2),
                     "severity": row.get("severity", "")})
    return {"seconds": round((last or 0) - (first or 0), 1), "incidents": incs, "raw_alarms": rt.filter.raw_alarms}


def judge(c: dict, r: dict) -> dict:
    fam = c["family"]
    out = {"positive": fam is not None, "detected": False, "delay_s": None, "early": 0}
    mine = [i for i in r["incidents"] if i["type"] == fam] if fam else []
    if fam and c["events"]:
        a, b = c["events"][0]
        good = [i for i in mine if a - EARLY_MARGIN <= i["ts"] <= b + (10 if fam == "accident" else 0)]
        out["early"] = len([i for i in mine if i["ts"] < a - EARLY_MARGIN])
        if good:
            out["detected"], out["delay_s"] = True, round(good[0]["ts"] - a, 2)
    elif fam:  # no onset labels (ABODA, demo): any incident of the family counts
        out["detected"] = bool(mine)
    # false alarms: incidents of the three PS families that do not belong to this clip's event
    out["fa"] = {f: len([i for i in r["incidents"] if i["type"] == f]) for f in ("accident", "crowd", "baggage")
                 if f != fam}
    out["other_types"] = sorted({i["type"] for i in r["incidents"]} - {"accident", "crowd", "baggage"})
    return out


def summarise(rows: list[dict]) -> dict:
    res = {}
    for split in sorted({r["split"] for r in rows}):
        rs = [r for r in rows if r["split"] == split and "judge" in r]
        s = {}
        for fam in ("accident", "crowd", "baggage"):
            pos = [r for r in rs if r["family"] == fam]
            neg = [r for r in rs if r["family"] != fam]
            tp = sum(r["judge"]["detected"] for r in pos)
            early = sum(r["judge"]["early"] for r in pos)
            fa = sum(r["judge"]["fa"].get(fam, 0) for r in neg)
            neg_h = sum(r["result"]["seconds"] for r in neg) / 3600
            fp = fa + early
            p = tp / (tp + fp) if tp + fp else None
            rc = tp / len(pos) if pos else None
            f1 = 2 * p * rc / (p + rc) if p and rc else (0.0 if pos else None)
            delays = [r["judge"]["delay_s"] for r in pos if r["judge"]["delay_s"] is not None]
            s[fam] = {"clips": len(pos), "detected": tp, "recall": None if rc is None else round(rc, 3),
                      "precision": None if p is None else round(p, 3), "f1": None if f1 is None else round(f1, 3),
                      "early_alarms": early, "false_alarms": fa, "negative_camera_hours": round(neg_h, 3),
                      "fa_per_camera_hour": round(fa / neg_h, 1) if neg_h else None,
                      "median_delay_s": round(float(np.median(delays)), 2) if delays else None}
        res[split] = s
    return res


def main() -> None:
    split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "all"
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
    clips = ucf_clips() + umn_clips() + aboda_clips() + avss_clips() + demo_clips()
    if "--build-tracks" in sys.argv:
        build_tracks(sorted((c for c in clips if c["kind"] == "video"), key=lambda c: c["split"] != "test"))
        return
    if split != "all":
        clips = [c for c in clips if c["split"] in split.split(",")]
    if "--kind" in sys.argv:
        clips = [c for c in clips if c["kind"] == sys.argv[sys.argv.index("--kind") + 1]]
    rows = []
    t0 = time.time()
    for c in clips:
        r = replay(c)
        row = {k: c[k] for k in ("name", "split", "family")}
        if "skipped" in r:
            row["skipped"] = r["skipped"]
        else:
            row.update(result=r, judge=judge(c, r))
        rows.append(row)
    summary = summarise(rows)
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "note": "REAL footage, cached detections replayed",
           "splits": "see training/real_eval.py docstring", "summary": summary,
           "skipped": [r["name"] for r in rows if "skipped" in r], "runtime_s": round(time.time() - t0),
           "rows": rows}
    name = f"real_eval{'_' + tag if tag else ''}.json"
    (ROOT / "docs" / "results" / name).write_text(json.dumps(out, indent=1))
    print(json.dumps(summary))
    if out["skipped"]:
        print("skipped (no cache):", out["skipped"])


if __name__ == "__main__":
    main()
