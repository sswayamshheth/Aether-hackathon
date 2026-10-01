"""Phase B: unify every dataset's labels into one events file per task.

    backend\\.venv\\Scripts\\python training\\prepare_labels.py

Writes
  data/labels/accident_events.csv, crowd_events.csv, baggage_events.csv
    columns: video_path, fps, event_type, start_frame, end_frame, start_s, end_s, bbox,
             camera_view, source, licence, split
    One row per labelled interval. A video with no incident gets one "normal" row covering it.
  data/labels/splits.json   the video-level split (train / val / test), frozen once written
  data/demo_eval/manifest.json   5-10 CCTV-style clips per task for the final real-world check

Splits are by video, never by frame, with a fixed seed, and are frozen: if splits.json
exists, existing videos keep their split and only new videos are assigned. Near-duplicate
videos (difference hash of three frames) are forced into the same split, so the same
footage cannot sit in train and test. The team's own videos (data/custom) are always in
train: the team asked for them to be trained on; they are evaluated leave-one-video-out
instead, and they are in demo_eval.
"""
from __future__ import annotations

import csv
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app import config  # noqa: E402

RAW = ROOT / "data" / "raw"
BENCH = ROOT / "data" / "bench"
LABELS = ROOT / "data" / "labels"
LABELS.mkdir(parents=True, exist_ok=True)
FIELDS = ["video_path", "fps", "event_type", "start_frame", "end_frame", "start_s", "end_s", "bbox",
          "camera_view", "source", "licence", "split"]
ACCIDENT_WORDS = re.compile(r"collid|collision|crash|accident|\bhit|overturn|roll ?over|flip|rear-end|t-bone|"
                            r"lose[s]? control|spin|smash|struck|strike|knock", re.I)
SEED = 20261001
SPLIT = {"train": 0.6, "val": 0.2, "test": 0.2}


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def probe(p: Path) -> tuple[float, int]:
    cap = cv2.VideoCapture(str(p))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return fps, n


def row(p: Path, event: str, s: float, e: float, source: str, licence: str, view: str = "cctv",
        bbox: str = "", fps: float | None = None) -> dict:
    fps = fps or probe(p)[0]
    return {"video_path": rel(p), "fps": round(fps, 3), "event_type": event,
            "start_frame": int(round(s * fps)), "end_frame": int(round(e * fps)),
            "start_s": round(s, 2), "end_s": round(e, 2), "bbox": bbox, "camera_view": view,
            "source": source, "licence": licence, "split": ""}


def whole(p: Path, event: str, source: str, licence: str) -> dict:
    fps, n = probe(p)
    return row(p, event, 0.0, n / fps, source, licence, fps=fps)


def mmss(t: str) -> float:
    m, s = t.split(":")
    return int(m) * 60 + float(s)


# ------------------------------------------------------------------ accident
def accident_rows() -> list[dict]:
    rows = []
    ann = {}
    for line in (BENCH / "_raw" / "ucf_temporal_annotations.txt").read_text().splitlines():
        p = line.split()
        if len(p) >= 6:
            ann[p[0]] = (p[1], [int(x) for x in p[2:6]])
    ucf = {p.name: p for d in ("ucf_more", "ucf_road") for p in (BENCH / "_raw" / d).glob("*.mp4")}
    lic = "UCF-Crime research dataset (HF mirror AllenXeon/ucf_crime, CC0-1.0 label)"
    for name, p in sorted(ucf.items()):
        if name not in ann or ann[name][0] not in {"RoadAccidents", "Normal"}:
            continue
        cls, w = ann[name]
        if cls == "Normal":
            rows.append(whole(p, "normal", "UCF-Crime", lic))
            continue
        fps = probe(p)[0]
        for i in (0, 2):
            if w[i] >= 0:  # UCF annotations count frames at 30 fps
                rows.append(row(p, "accident", w[i] / 30.0, w[i + 1] / 30.0, "UCF-Crime", lic, fps=fps))
    for name, onset in {"1.mp4": 4.0, "2.mp4": 5.0, "3.mp4": 22.0}.items():
        p = ROOT / "data" / "custom" / name
        if p.exists():
            fps, n = probe(p)
            rows.append(row(p, "accident", onset, min(n / fps, onset + 10.0), "team video", "team's own", fps=fps))

    d = json.loads((RAW / "nvidia_traffic" / "train" / "temporal_localization.json").read_text(encoding="utf-8"))
    tb = RAW / "tadbench"
    per_video: dict[str, list] = {}
    for it in d["items"]:
        if it["video_id"].startswith("TAD-benchmark/"):
            per_video.setdefault(it["video_id"], []).append(it)
    lic_tb = "TADBench (no licence stated); timestamps from NVIDIA PhysicalAI-Traffic-Anomaly-Reasoning, CC-BY-4.0"
    for p in sorted(tb.rglob("*.mp4")):
        vid = p.relative_to(tb).as_posix()
        is_acc = "/accident" in vid.split("TAD-benchmark", 1)[1]
        items = per_video.get(vid, [])
        spans = []
        for it in items:
            if not ACCIDENT_WORDS.search(it["question"]):
                continue
            try:
                a = json.loads(it["answer"])
                spans.append((mmss(a["start"]), mmss(a["end"])))
            except Exception:  # noqa: BLE001
                continue
        if is_acc and spans:
            fps = probe(p)[0]
            for s, e in spans:
                rows.append(row(p, "accident", s, max(e, s + 1.0), "TADBench", lic_tb, fps=fps))
        elif is_acc:
            # an accident clip without a timestamped collision question: the clip is known to
            # contain an accident but not when, so it is kept for clip-level evaluation only
            r = whole(p, "accident_untimed", "TADBench", lic_tb)
            rows.append(r)
        else:
            rows.append(whole(p, "normal", "TADBench", lic_tb))
    return rows


# ------------------------------------------------------------------ crowd
MED_LABEL = {1: "panic", 2: "fight", 3: "congestion", 4: "obstacle", 5: "normal"}


def crowd_rows() -> list[dict]:
    rows = []
    med = RAW / "med"
    src = (med / "Motion Emotion Dataset(MED) annotation" / "dataset_frames_abnormal_labeling.m").read_text()
    lic = "MED (Rabiee et al., AVSS 2016), research use"
    for block in re.findall(r"video(\d+) = zeros\(1,(\d+)\);(.*?)behavelabels", src, re.S):
        idx, n, body = int(block[0]), int(block[1]), block[2]
        p = med / f"{idx:03d}.mp4"
        if not p.exists():
            continue
        fps = probe(p)[0]
        # replay the MATLAB assignments in order: later lines overwrite earlier ones (some
        # files first write the video number as a placeholder)
        lab_arr = np.zeros(n, dtype=int)
        for a, b, v in re.findall(r"\(1,(\d+):(\d+|end)\)\s*=\s*(\d+)", body):
            lab_arr[int(a) - 1:(n if b == "end" else int(b))] = int(v)
        s = 0
        for i in range(1, n + 1):
            if i == n or lab_arr[i] != lab_arr[s]:
                if lab_arr[s] in MED_LABEL:  # 0 = unlabelled tail
                    rows.append({**row(p, MED_LABEL[int(lab_arr[s])], s / fps, i / fps, "MED", lic, fps=fps),
                                 "start_frame": s, "end_frame": i})
                s = i
    umn = BENCH / "crowd" / "umn_all.avi"
    lab = json.loads((BENCH / "crowd" / "umn_labels.json").read_text())
    fps = lab["fps"]
    for sc in lab["scenes"]:  # one "video" per scene: the same file with a frame range
        rows.append({**row(umn, "normal", sc["start"] / fps, sc["onset"] / fps, "UMN", "UMN, research use", fps=fps),
                     "video_path": f"{rel(umn)}#{sc['start']}-{sc['end']}"})
        rows.append({**row(umn, "panic", sc["onset"] / fps, sc["end"] / fps, "UMN", "UMN, research use", fps=fps),
                     "video_path": f"{rel(umn)}#{sc['start']}-{sc['end']}"})
    ped2 = RAW / "ucsd" / "UCSD_Anomaly_Dataset.v1p2" / "UCSDped2"
    gt = re.findall(r"gt_frame = \[(\d+):(\d+)\]", (ped2 / "Test" / "UCSDped2.m").read_text())
    out = RAW / "ucsd" / "mp4"
    out.mkdir(exist_ok=True)
    lic_u = "UCSD Anomaly Detection Dataset, research use"
    for part in ("Train", "Test"):
        for d in sorted(q for q in (ped2 / part).iterdir() if q.is_dir() and not q.name.endswith("_gt")):
            mp4 = out / f"ped2_{d.name}.mp4"
            if not mp4.exists():  # 10 fps tif sequences -> mp4 so every tool reads the same way
                subprocess.run([str(config.FFMPEG), "-v", "error", "-y", "-framerate", "10", "-i", str(d / "%03d.tif"),
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)], check=True)
            n = len(list(d.glob("*.tif")))
            if part == "Test":
                k = int(d.name.replace("Test", "")) - 1
                a, b = int(gt[k][0]), int(gt[k][1])
                if a > 1:
                    rows.append(row(mp4, "normal", 0, (a - 1) / 10, "UCSD Ped2", lic_u, fps=10))
                rows.append(row(mp4, "non_pedestrian", (a - 1) / 10, b / 10, "UCSD Ped2", lic_u, fps=10))
            else:
                rows.append(row(mp4, "normal", 0, n / 10, "UCSD Ped2", lic_u, fps=10))
    return rows


# ------------------------------------------------------------------ baggage
def baggage_rows() -> list[dict]:
    rows = []
    avss = RAW / "uam_aod" / "datasets" / "AVSS2007"
    lic = "AVSS 2007 / i-LIDS AB, research use; ground truth from the UAM AOD survey"
    for gt in sorted(avss.glob("*.txt")):
        x = gt.read_text()
        fps = float(re.search(r'FRAMERATE">\s*<data:fvalue value="([\d.]+)"', x).group(1))
        mpg = avss / gt.name.replace(".txt", ".mpg")
        for span, name, bh, bw, bx, by in re.findall(
                r'<object framespan="(\d+:\d+)" id="\d+" name="(\w+)">\s*<attribute name="BoundingBox">\s*'
                r'<data:bbox height="(\d+)" width="(\d+)" x="(\d+)" y="(\d+)"', x):
            a, b = (int(v) for v in span.split(":"))
            ev = "abandoned" if name == "AbandonedObject" else "put_object"
            rows.append({**row(mpg, ev, a / fps, b / fps, "AVSS 2007 (UAM GT)", lic, fps=fps,
                               bbox=f"{bx},{by},{bw},{bh}"), "start_frame": a, "end_frame": b})
    for p in sorted((BENCH / "_raw" / "ABODA").glob("*.avi")):
        rows.append(whole(p, "abandoned_untimed", "ABODA", "ABODA, no licence file"))
    return rows


# ------------------------------------------------------------------ splits
def dhash(p: str) -> list[int]:
    path, _, rng = p.partition("#")
    cap = cv2.VideoCapture(str(ROOT / path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    lo, hi = (int(v) for v in rng.split("-")) if rng else (0, max(n - 1, 1))
    out = []
    for f in (lo + (hi - lo) // 4, lo + (hi - lo) // 2, lo + 3 * (hi - lo) // 4):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if not ok:
            continue
        g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (9, 8))
        bits = (g[:, 1:] > g[:, :-1]).flatten()
        out.append(int("".join("1" if b else "0" for b in bits), 2))
    cap.release()
    return out


def assign_splits(all_rows: dict[str, list[dict]]) -> dict[str, str]:
    path = LABELS / "splits.json"
    frozen = json.loads(path.read_text()) if path.exists() else {}
    videos = sorted({r["video_path"] for rows in all_rows.values() for r in rows})
    hashes = {v: dhash(v) for v in videos}
    # union near-duplicates (at most 6 of 64 bits different on every sampled frame)
    parent = {v: v for v in videos}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for i, a in enumerate(videos):
        for b in videos[i + 1:]:
            ha, hb = hashes[a], hashes[b]
            if ha and hb and len(ha) == len(hb) and all(bin(x ^ y).count("1") <= 6 for x, y in zip(ha, hb)):
                parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for v in videos:
        groups.setdefault(find(v), []).append(v)
    rng = random.Random(SEED)
    split = dict(frozen)
    dup_groups = 0
    for g in sorted(groups.values(), key=lambda x: x[0]):
        if len(g) > 1:
            dup_groups += 1
        known = [split[v] for v in g if v in split]
        if any("data/custom/" in v for v in g):
            s = "train"
        elif known:
            s = known[0]
        else:
            r = rng.random()
            s = "train" if r < SPLIT["train"] else "val" if r < SPLIT["train"] + SPLIT["val"] else "test"
        for v in g:
            split[v] = s
    path.write_text(json.dumps(split, indent=1, sort_keys=True))
    print(f"splits: {len(videos)} videos, {dup_groups} near-duplicate groups kept together, frozen in {rel(path)}")
    return split


def main() -> None:
    tasks = {"accident": accident_rows(), "crowd": crowd_rows(), "baggage": baggage_rows()}
    split = assign_splits(tasks)
    for task, rows in tasks.items():
        for r in rows:
            r["split"] = split[r["video_path"]]
        with (LABELS / f"{task}_events.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        vids = {r["video_path"]: r["split"] for r in rows}
        by = {s: sum(1 for v in vids.values() if v == s) for s in ("train", "val", "test")}
        ev = {}
        for r in rows:
            ev[r["event_type"]] = ev.get(r["event_type"], 0) + 1
        print(f"{task}: {len(rows)} rows, {len(vids)} videos {by}, events {ev}")

    # demo_eval: CCTV clips that look like the demo feeds, from the test split where possible
    acc = [r for r in tasks["accident"] if r["event_type"] == "accident"]
    manifest = {
        "accident": sorted({r["video_path"] for r in acc if "data/custom/" in r["video_path"]})
        + sorted({r["video_path"] for r in acc if r["split"] == "test" and r["source"] == "TADBench"})[:5],
        "crowd": sorted({r["video_path"] for r in tasks["crowd"] if r["split"] == "test"
                         and r["event_type"] in {"panic", "fight"}})[:8],
        "baggage": sorted({r["video_path"] for r in tasks["baggage"]})[:8],
        "note": "Our own accident videos are in train (the team asked for them to be trained on) and are "
                "scored leave-one-video-out; everything else listed here is from the frozen test split, "
                "except baggage, where every labelled video is listed because there are so few.",
    }
    demo = ROOT / "data" / "demo_eval"
    demo.mkdir(parents=True, exist_ok=True)
    (demo / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print("demo_eval:", {k: len(v) for k, v in manifest.items() if k != "note"})


if __name__ == "__main__":
    main()
