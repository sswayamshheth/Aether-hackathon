"""Method B of the synthetic suite: pixel-level variants of real labelled clips.

    backend\\.venv\\Scripts\\python training\\synth\\pixel_variants.py [--only <clip>] [--tag name]

Each real clip is re-run through the full live pipeline (YOLO11n + ByteTrack + engines +
filter + incidents; auxiliary models limited to the accident model to keep CPU time
reasonable) with one image condition applied to every frame. Ground truth carries over from
the real labels. Writes docs/results/synthetic_pixel[_tag].json and the spec files
tests/scenarios/pixel_<family>/<id>.yaml.

Conditions: night, rain overlay, fog, heavy JPEG, low resolution, motion blur, camera shake,
sensor noise, infrared-style grayscale, dropped frames, partial occlusion mask. Plus the
unmodified clip as the reference run.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DRISHTI_AUX", "accident")
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "models")

import logging  # noqa: E402

logging.disable(logging.WARNING)

from app import config  # noqa: E402
from app.db import Store  # noqa: E402
from app.runtime import Pipeline, Runtime  # noqa: E402

CLIPS = {  # name: (path, profile, family, event window in clip seconds or None = any time)
    "demo_accident_ucf010": (config.DEMO / "clips" / "cam1.mp4", "traffic", "accident", (230 / 30, 270 / 30 + 10)),
    "demo_crowd_umn4": (config.DEMO / "clips" / "cam4.mp4", "public", "crowd", ((3219 - 2685) / 30 - 1, (3428 - 2685) / 30 + 3)),
    "demo_baggage_aboda9": (config.DEMO / "clips" / "cam3.mp4", "public", "baggage", None),
}
CONDS = ["reference", "night", "rain", "fog", "jpeg_q10", "low_res", "motion_blur", "shake", "noise", "infrared",
         "dropped_frames", "occlusion_mask"]


def apply(img: np.ndarray, cond: str, rng: np.random.Generator, i: int) -> np.ndarray | None:
    h, w = img.shape[:2]
    if cond == "night":
        out = (img.astype(np.float32) * 0.3)
        out += rng.normal(0, 6, img.shape)
        return np.clip(out, 0, 255).astype(np.uint8)
    if cond == "rain":
        layer = np.zeros_like(img)
        for _ in range(250):
            x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
            cv2.line(layer, (x, y), (x + 3, y + 14), (200, 200, 200), 1)
        return cv2.addWeighted(cv2.blur(img, (2, 2)), 0.85, layer, 0.5, 0)
    if cond == "fog":
        return cv2.addWeighted(img, 0.45, np.full_like(img, 200), 0.55, 0)
    if cond == "jpeg_q10":
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 10])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if cond == "low_res":
        return cv2.resize(cv2.resize(img, (w // 4, h // 4), interpolation=cv2.INTER_AREA), (w, h))
    if cond == "motion_blur":
        k = np.zeros((9, 9), np.float32)
        k[4, :] = 1 / 9
        return cv2.filter2D(img, -1, k)
    if cond == "shake":
        dx, dy = rng.normal(0, 6), rng.normal(0, 4)
        return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (w, h), borderMode=cv2.BORDER_REFLECT)
    if cond == "noise":
        return np.clip(img.astype(np.int16) + rng.normal(0, 18, img.shape).astype(np.int16), 0, 255).astype(np.uint8)
    if cond == "infrared":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        g = cv2.equalizeHist(255 - g) if False else cv2.equalizeHist(g)
        return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    if cond == "dropped_frames":
        return None if rng.random() < 0.3 else img
    if cond == "occlusion_mask":
        out = img.copy()
        cv2.rectangle(out, (int(w * 0.05), int(h * 0.55)), (int(w * 0.3), h), (40, 40, 40), -1)  # a pillar / sign
        return out
    return img


def run(name: str, cond: str) -> dict:
    path, profile, fam, win = CLIPS[name]
    rng = np.random.default_rng(abs(hash((name, cond))) % 2**32)
    store = Store(":memory:")
    rt = Runtime(store, live=False)
    cam = {"id": "pix", "name": "pix", "source": str(path), "kind": "file", "area": "pix", "profile": profile}
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps / config.TARGET_FPS))
    pipe = Pipeline(cam, rt, fps=fps / step)
    idx, ts, t0 = -1, 0.0, time.time()
    while True:
        ok, img = cap.read()
        if not ok:
            break
        idx += 1
        if idx % step:
            continue
        ts = idx / fps
        img2 = apply(img, cond, rng, idx)
        if img2 is None:
            continue
        pipe.process(img2, ts, idx)
    cap.release()
    rt.filter.flush("pix", ts)
    incs = [{"type": h["type"], "subtype": h["subtype"], "ts": round(h["ts"], 2),
             "severity": (store.incident(h["id"]) or {}).get("severity", "")} for h in rt.history]
    mine = [i for i in incs if i["type"] == fam]
    if win:
        good = [i for i in mine if win[0] - 1 <= i["ts"] <= win[1]]
        early = [i for i in mine if i["ts"] < win[0] - 1]
    else:
        good, early = mine, []
    other_fa = [i for i in incs if i["type"] in ("accident", "crowd", "baggage") and i["type"] != fam]
    return {"id": f"{name}__{cond}", "clip": name, "condition": cond, "family": fam, "passed": bool(good) and not early,
            "detected": bool(good), "delay_s": round(good[0]["ts"] - win[0], 2) if good and win else None,
            "early": len(early), "false_alarms_other_families": len(other_fa), "incidents": incs,
            "seconds": round(ts, 1), "secs": round(time.time() - t0, 1)}


def main() -> None:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
    rows = []
    for name in CLIPS:
        if only and only != name:
            continue
        fam = CLIPS[name][2]
        d = ROOT / "tests" / "scenarios" / f"pixel_{fam}"
        d.mkdir(parents=True, exist_ok=True)
        for cond in CONDS:
            spec = {"id": f"{name}__{cond}", "category": f"pixel_{fam}", "method": "B (pixel-level variant of a real clip)",
                    "description": f"real clip {name} with condition '{cond}' applied to every frame",
                    "source_clip": str(CLIPS[name][0].relative_to(ROOT)), "condition": cond,
                    "expected": {"event": fam, "window_s": list(CLIPS[name][3]) if CLIPS[name][3] else "any time"}}
            (d / f"{name}__{cond}.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
            r = run(name, cond)
            rows.append(r)
            print(f"{r['id']:45s} {'PASS' if r['passed'] else 'FAIL'} delay={r['delay_s']} early={r['early']} "
                  f"other_fa={r['false_alarms_other_families']} {r['secs']}s", flush=True)
    by = {}
    for r in rows:
        m = by.setdefault(r["family"], {"runs": 0, "passed": 0, "detected": 0})
        m["runs"] += 1
        m["passed"] += r["passed"]
        m["detected"] += r["detected"]
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "method": "B: pixel-level variants of real clips (synthetic)",
           "aux_models": sorted(config.ENABLED_AUX), "per_family": by, "rows": rows}
    (ROOT / "docs" / "results" / f"synthetic_pixel{'_' + tag if tag else ''}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(by))


if __name__ == "__main__":
    main()
