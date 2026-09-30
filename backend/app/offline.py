"""Run the full pipeline over a video file in video time (no threads, no dashboard).
Used by the evaluation scripts and to build the demo-mode detection cache."""
from __future__ import annotations

import time
from pathlib import Path

import cv2

from . import config
from .db import Store
from .runtime import Pipeline, Runtime


def run_clip(path: str | Path, profile: str = "mixed", cam_id: str = "eval",
             max_seconds: float | None = None, mask_rows: int = 0, record: bool = False,
             zones: list[dict] | None = None, start_frame: int = 0,
             end_frame: int | None = None) -> dict:
    store = Store(":memory:")
    for z in zones or []:
        store.add_zone(cam_id, z["name"], z["kind"], z["points"])
    rt = Runtime(store, live=False)
    cap = cv2.VideoCapture(str(path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(src_fps / config.TARGET_FPS))
    cam = {"id": cam_id, "name": cam_id, "source": str(path), "kind": "file", "area": cam_id,
           "profile": profile}
    pipe = Pipeline(cam, rt, fps=src_fps / step, record=record)
    if start_frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    idx, n, ts = start_frame - 1, 0, 0.0
    probs: list[tuple[int, float]] = []
    t0 = time.perf_counter()
    while True:
        ok, image = cap.read()
        if not ok:
            break
        idx += 1
        if end_frame is not None and idx > end_frame:
            break
        if idx % step:
            continue
        ts = idx / src_fps
        if max_seconds and ts - start_frame / src_fps > max_seconds:
            break
        if mask_rows:
            image[:mask_rows] = 0
        pipe.process(image, ts, idx)
        probs.append((idx, round(pipe.last_prob, 4)))
        n += 1
    cap.release()
    elapsed = time.perf_counter() - t0
    rt.filter.flush(cam_id, ts)
    return {"clip": Path(path).name, "frames": n, "seconds": round(ts - start_frame / src_fps, 2),
            "src_fps": src_fps,
            "step": step, "proc_fps": round(n / max(elapsed, 1e-6), 2),
            "incidents": rt.history, "suppressed": rt.suppressed,
            "raw_alarms": rt.filter.raw_alarms, "crowd_probs": probs, "cache": pipe.record}
