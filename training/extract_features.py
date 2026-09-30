"""Run every model over the labelled clips once and cache the raw outputs.

    backend\\.venv\\Scripts\\python training\\extract_features.py [--only NAME] [--limit N]

For each clip, a segment around the annotated incident (or the first 45 s of a normal
clip) is sampled at the live rate (10 fps). Pass "tracks" runs the COCO detector every
second sampled frame plus ByteTrack; one pass per auxiliary model then runs that model at
its live cadence. One model is loaded at a time, so memory stays low, and each finished
pass is saved, so the script can be stopped and resumed.

Output: data/cache/features/<clip>.json, in the same per-frame format as the demo cache,
so the pipeline can replay any clip without running a model (training/train_verifiers.py).
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "models")

from app import config  # noqa: E402

RAW = ROOT / "data" / "bench" / "_raw"
OUT = ROOT / "data" / "cache" / "features"
OUT.mkdir(parents=True, exist_ok=True)
SEG_S = 45.0
PRE_S = 15.0
# the accident model is slow on a CPU; it only matters on road footage and normal clips
ACCIDENT_CLASSES = {"RoadAccidents", "Normal"}
CAP = {"Normal": 25, "Burglary": 4, "Stealing": 3}


def clip_list() -> list[dict]:
    ann = {}
    for line in (RAW / "ucf_temporal_annotations.txt").read_text().splitlines():
        p = line.split()
        if len(p) >= 6:
            ann[p[0]] = (p[1], [int(x) for x in p[2:6]])
    files = {p.name: p for p in list((RAW / "ucf_more").glob("*.mp4")) + list((RAW / "ucf_road").glob("*.mp4"))}
    per_class: dict[str, int] = {}
    out = []
    for name in sorted(files):
        if name not in ann:
            continue
        cls, w = ann[name]
        if per_class.get(cls, 0) >= CAP.get(cls, 99):
            continue
        per_class[cls] = per_class.get(cls, 0) + 1
        cap = cv2.VideoCapture(str(files[name]))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        cap.release()
        windows = [(w[i] / 30.0, w[i + 1] / 30.0) for i in (0, 2) if w[i] >= 0]
        start = max(0.0, windows[0][0] - PRE_S) if windows else 0.0
        end = min(dur, start + SEG_S)
        out.append({"clip": name, "path": str(files[name]), "class": cls, "windows": windows,
                    "start_s": round(start, 2), "end_s": round(end, 2), "fps": fps})
    return out


def frames(meta: dict):
    fps = meta["fps"]
    step = max(1, round(fps / config.TARGET_FPS))
    cap = cv2.VideoCapture(meta["path"])
    first = int(meta["start_s"] * fps)
    first -= first % step
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    idx = first - 1
    while True:
        ok, img = cap.read()
        if not ok:
            break
        idx += 1
        if idx / fps > meta["end_s"]:
            break
        if idx % step == 0:
            yield idx, idx / fps, img
    cap.release()


def load(meta: dict) -> dict:
    p = OUT / f"{Path(meta['clip']).stem}.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"meta": meta, "passes": [], "frames": {}}


def save(data: dict) -> None:
    (OUT / f"{Path(data['meta']['clip']).stem}.json").write_text(json.dumps(data, separators=(",", ":")))


def pass_tracks(clips: list[dict]) -> None:
    import numpy as np

    from app.detector import Tracker, get_detector
    from app.runtime import BAG_IDS
    from app.schema import Track

    det = get_detector()
    for meta in clips:
        data = load(meta)
        if "tracks" in data["passes"]:
            continue
        tracker, n, t0 = Tracker(config.TARGET_FPS / config.DETECT_EVERY), 0, time.time()
        for idx, ts, img in frames(meta):
            fresh = n % config.DETECT_EVERY == 0
            n += 1
            rec = data["frames"].setdefault(str(idx), {"fresh": fresh, "tracks": [], "aux": {}})
            rec["fresh"] = fresh
            if fresh:
                boxes = det.detect(img)
                is_bag = np.isin(boxes.cls.astype(int), BAG_IDS)
                moving = tracker.update(boxes[~is_bag], img)
                bags = [Track(0, config.COCO[int(c)], tuple(float(v) for v in b), float(p))
                        for b, c, p in zip(boxes.xyxy[is_bag], boxes.cls[is_bag], boxes.conf[is_bag])]
                tracks = [t for t in moving if t.cls not in config.BAGS] + bags
                rec["tracks"] = [[t.id, t.cls, *[round(v, 1) for v in t.box], round(t.conf, 3)] for t in tracks]
        data["passes"].append("tracks")
        save(data)
        print(f"tracks {meta['clip']} {n} frames {time.time() - t0:.0f}s", flush=True)


def pass_aux(clips: list[dict], name: str) -> None:
    from app import aux_models

    config.ENABLED_AUX.clear()
    config.ENABLED_AUX.add(name)
    aux_models._models = None
    model = aux_models.get_models().get(name)
    if not model or not model.available:
        print(f"{name}: model not available, skipped", flush=True)
        return
    for meta in clips:
        if name == "accident" and meta["class"] not in ACCIDENT_CLASSES:
            continue
        data = load(meta)
        if name in data["passes"]:
            continue
        last, n, t0 = -1e9, 0, time.time()
        for idx, ts, img in frames(meta):
            if ts - last >= model.every_s:
                last = ts
                data["frames"].setdefault(str(idx), {"fresh": False, "tracks": [], "aux": {}})["aux"][name] = model.run(img)
                n += 1
        data["passes"].append(name)
        save(data)
        print(f"{name} {meta['clip']} {n} calls {time.time() - t0:.0f}s", flush=True)
    aux_models._models = None
    del model
    gc.collect()


def main() -> None:
    clips = clip_list()
    if "--limit" in sys.argv:
        clips = clips[: int(sys.argv[sys.argv.index("--limit") + 1])]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    by_cls: dict[str, int] = {}
    for c in clips:
        by_cls[c["class"]] = by_cls.get(c["class"], 0) + 1
    print(f"{len(clips)} clips: {by_cls}", flush=True)
    (OUT / "clips.json").write_text(json.dumps(clips, indent=1))
    for name in ["tracks", "fire", "weapon", "fall", "violence", "scene", "accident"]:
        if only and name != only:
            continue
        t0 = time.time()
        pass_tracks(clips) if name == "tracks" else pass_aux(clips, name)
        print(f"=== pass {name} done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
