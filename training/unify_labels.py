"""Unify every time-stamped label we have on disk into one CSV per task.

    backend\\.venv\\Scripts\\python training\\unify_labels.py

Writes data/labels/<task>_events.csv with columns
  video_path, fps, event_type, start_frame, end_frame, start_s, end_s, bbox, camera_view,
  source, licence, split
One row per labelled event; normal videos get one row with event_type "normal". Splits are
by video (never by frame): the evaluation splits of training/real_eval.py where a video is
used there, otherwise a stable hash of the file name (70 / 15 / 15).
"""
from __future__ import annotations

import csv
import json
import re
import sys
import zlib
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BENCH = ROOT / "data" / "bench"
OUT = ROOT / "data" / "labels"
sys.path.insert(0, str(ROOT / "training"))

COLS = ["video_path", "fps", "event_type", "start_frame", "end_frame", "start_s", "end_s", "bbox", "camera_view",
        "source", "licence", "split"]


def hsplit(name: str) -> str:
    h = zlib.crc32(name.encode()) % 100
    return "train" if h < 70 else ("val" if h < 85 else "test")


def vinfo(p: Path) -> tuple[float, int]:
    cap = cv2.VideoCapture(str(p))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return fps, n


def row(path, fps, ev, s_f, e_f, view, source, licence, split, bbox=""):
    return {"video_path": str(Path(path).relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path),
            "fps": round(fps, 3), "event_type": ev, "start_frame": s_f, "end_frame": e_f,
            "start_s": round(s_f / fps, 2) if s_f != "" else "", "end_s": round(e_f / fps, 2) if e_f != "" else "",
            "bbox": bbox, "camera_view": view, "source": source, "licence": licence, "split": split}


def accident() -> list[dict]:
    from real_eval import ucf_clips

    rows = []
    for c in ucf_clips():
        if c["meta"]["class"] not in ("RoadAccidents", "Normal"):
            continue
        fps = c["meta"]["fps"]
        if c["family"] == "accident":
            for a, b in c["events"]:
                rows.append(row(c["path"], fps, "accident", int(a * fps), int(b * fps), "cctv", "UCF-Crime",
                                "research use (UCF-Crime terms)", c["split"]))
        else:
            rows.append(row(c["path"], fps, "normal", "", "", "cctv", "UCF-Crime", "research use (UCF-Crime terms)",
                            c["split"]))
    for name, onset in {"1.mp4": 4.0, "2.mp4": 5.0, "3.mp4": 22.0}.items():
        p = ROOT / "data" / "custom" / name
        if p.exists():
            fps, n = vinfo(p)
            rows.append(row(p, fps, "accident", int(onset * fps), min(n, int((onset + 10) * fps)), "cctv",
                            "team videos (HCQ_D36)", "own", "train"))
    # TADBench, timed by the NVIDIA AI City 2026 Track 3 temporal-localisation labels
    tl = RAW / "nvidia_traffic" / "train" / "temporal_localization.json"
    tad = RAW / "tadbench"
    if tl.exists():
        items = json.loads(tl.read_text(encoding="utf-8"))["items"]
        seen = set()
        for it in items:
            vid = it["video_id"]
            if not vid.startswith("TAD-benchmark/") or vid in seen:
                continue
            p = tad / vid
            if not p.exists():
                continue
            seen.add(vid)
            ans = it.get("answer") or it.get("label") or {}
            if isinstance(ans, str):
                try:
                    ans = json.loads(ans)
                except ValueError:
                    ans = {}
            def sec(x):
                m, s = str(x).split(":")
                return int(m) * 60 + float(s)
            try:
                a, b = sec(ans["start"]), sec(ans["end"])
            except (KeyError, ValueError):
                continue
            fps, _ = vinfo(p)
            rows.append(row(p, fps, "accident", int(a * fps), int(b * fps), "cctv",
                            "TAD-benchmark (timing: NVIDIA AI City 2026 Track 3)", "CC-BY-4.0 labels; TAD research use",
                            hsplit(vid)))
        for p in sorted((tad / "TAD-benchmark").rglob("*.mp4")):
            if "normal" in p.parts[-2]:
                fps, _ = vinfo(p)
                rows.append(row(p, fps, "normal", "", "", "cctv", "TAD-benchmark", "research use",
                                hsplit(p.name)))
    return rows


def crowd() -> list[dict]:
    from real_eval import UMN_TEST

    rows = []
    lab = json.loads((BENCH / "crowd" / "umn_labels.json").read_text())
    for si, s in enumerate(lab["scenes"]):
        rows.append(row(BENCH / "crowd" / "umn_all.avi", lab["fps"], "panic", s["onset"], s["end"], "cctv (staged)",
                        f"UMN scene {si}", "research use", "test" if si in UMN_TEST else "val"))
    # MED: per-frame behaviour labels in a MATLAB script
    m = (RAW / "med" / "Motion Emotion Dataset(MED) annotation" / "dataset_frames_abnormal_labeling.m")
    names = {1: "panic", 2: "fight", 3: "congestion", 4: "obstacle"}
    if m.exists():
        txt = m.read_text(encoding="utf-8", errors="ignore")
        for v, a, b, k in re.findall(r"video(\d+)\(1,(\d+):(\d+|end)\)\s*=\s*(\d)", txt):
            k = int(k)
            if k not in names:
                continue
            p = RAW / "med" / f"{int(v):03d}.mp4"
            if not p.exists():
                continue
            fps, n = vinfo(p)
            e = n if b == "end" else int(b)
            rows.append(row(p, fps, names[k], int(a) - 1, e - 1, "cctv (staged)", "MED (Motion Emotion Dataset)",
                            "research use", hsplit(p.name)))
    # UCSD Ped2: frame spans of anomalies (bikes, carts, skaters in a walkway)
    spec = RAW / "ucsd" / "UCSD_Anomaly_Dataset.v1p2" / "UCSDped2" / "Test" / "UCSDped2.m"
    if spec.exists():
        txt = spec.read_text(errors="ignore")
        for n_, a, b in re.findall(r"TestVideoFile\{(?:end\+1|(\d+))\}\.gt_frame\s*=\s*\[(\d+):(\d+)\]", txt) or []:
            pass
        spans = re.findall(r"gt_frame\s*=\s*\[(\d+):(\d+)\]", txt)
        for i, (a, b) in enumerate(spans, 1):
            p = RAW / "ucsd" / "mp4" / f"ped2_Test{i:03d}.mp4"
            fps = vinfo(p)[0] if p.exists() else 10.0
            rows.append(row(p, fps, "non-pedestrian in walkway", int(a) - 1, int(b) - 1, "cctv", "UCSD Ped2",
                            "research use", hsplit(p.name)))
    return rows


def baggage() -> list[dict]:
    from real_eval import avss_clips

    rows = []
    for c in avss_clips():
        fps = 25.0
        rows.append(row(c["path"], fps, "bag put down", int(c["put_s"] * fps), "", "cctv", "AVSS 2007 (UAM ground truth)",
                        "research use", "test"))
        rows.append(row(c["path"], fps, "abandoned (30 s rule)", int(c["abandoned_s"] * fps), "", "cctv",
                        "AVSS 2007 (UAM ground truth)", "research use", "test"))
    for p in sorted((BENCH / "baggage").glob("aboda_*.mp4")):
        fps, n = vinfo(p)
        rows.append(row(p, fps, "abandoned (no timestamp)", "", "", "cctv", "ABODA", "research use (no licence file)",
                        "val"))
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for task, fn in (("accident", accident), ("crowd", crowd), ("baggage", baggage)):
        rows = fn()
        with open(OUT / f"{task}_events.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, COLS)
            w.writeheader()
            w.writerows(rows)
        by = {}
        for r in rows:
            k = (r["source"].split(" (")[0].split(" scene")[0], r["event_type"], r["split"])
            by[k] = by.get(k, 0) + 1
        print(task, len(rows), "rows;", len({r["video_path"] for r in rows}), "videos")
        for k, v in sorted(by.items()):
            print("   ", k, v)


if __name__ == "__main__":
    main()
