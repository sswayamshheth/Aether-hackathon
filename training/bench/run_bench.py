"""Phase 1B bench harness. Runs each reference repo's model or logic on the same
clips in data/bench and writes raw measurements to docs/results/bench_<name>.json.

Nothing here decides pass/fail; summarise.py turns the raw series into BENCH.md.
Usage (from the project root, inside the reference venv):
    python training/bench/run_bench.py <task> [...]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import cv2
import psutil

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "data" / "bench"
REF = ROOT / "_reference"
OUT = ROOT / "docs" / "results"
OUT.mkdir(parents=True, exist_ok=True)

MAX_SECONDS = 40.0  # accident and normal clips are capped so every model sees the same footage


def rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1e6


def frames(path: Path, sample_fps: float, max_seconds: float | None = MAX_SECONDS):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / sample_fps))
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = i / fps
        if max_seconds and t > max_seconds:
            break
        if i % step == 0:
            yield i, t, frame
        i += 1
    cap.release()


def clips(*groups: str) -> list[Path]:
    out: list[Path] = []
    for g in groups:
        out += sorted(p for p in (BENCH / g).iterdir() if p.suffix in {".mp4", ".avi"})
    return out


def save(name: str, payload: dict) -> None:
    (OUT / f"bench_{name}.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote docs/results/bench_{name}.json")


# ---------------------------------------------------------------- accident weights
def accident_weights(name: str, weights: str, sample_fps: float = 2.0, imgsz: int = 640) -> None:
    from ultralytics import YOLO

    model = YOLO(weights)
    names = model.names
    res = {"name": name, "weights": weights, "classes": names, "sample_fps": sample_fps,
           "imgsz": imgsz, "clips": {}}
    n, infer_s = 0, 0.0
    for clip in clips("accident", "normal"):
        series = []
        for idx, t, frame in frames(clip, sample_fps):
            t0 = time.perf_counter()
            r = model.predict(frame, imgsz=imgsz, conf=0.10, verbose=False)[0]
            infer_s += time.perf_counter() - t0
            n += 1
            best: dict[str, float] = {}
            for c, p in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist()):
                k = names[int(c)]
                best[k] = max(best.get(k, 0.0), round(float(p), 3))
            series.append({"f": idx, "t": round(t, 2), "conf": best})
        res["clips"][clip.parent.name + "/" + clip.name] = series
        print(clip.name, len(series), "frames")
    res["frames"] = n
    res["infer_fps"] = round(n / infer_s, 2)
    res["rss_mb"] = round(rss_mb())
    save(name, res)


# ---------------------------------------------------------------- neyvur trajectory rules
def neyvur() -> None:
    repo = REF / "neyvur-traffic"
    os.chdir(repo)
    sys.path.insert(0, str(repo))
    from src.solution import detect_events

    res = {"name": "neyvur", "clips": {}}
    # first 4 accident clips only: this repo processes every frame, which is slow here
    for clip in clips("accident")[:4] + [BENCH / "normal" / "ucf_normal_006.mp4"]:
        t0 = time.perf_counter()
        try:
            events = detect_events(str(clip))
            err = None
        except Exception as e:  # noqa: BLE001
            events, err = [], repr(e)
        dt = time.perf_counter() - t0
        cap = cv2.VideoCapture(str(clip))
        nf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        res["clips"][clip.parent.name + "/" + clip.name] = {
            "events": events, "error": err, "seconds": round(dt, 1), "frames": nf,
            "fps": round(nf / dt, 1)}
        print(clip.name, len(events), "events", err or "")
    res["rss_mb"] = round(rss_mb())
    save("neyvur", res)


# ---------------------------------------------------------------- baria: abandoned object + crowd
def _track(model, frame, classes):
    r = model.track(frame, persist=True, classes=classes, conf=0.25, imgsz=640,
                    tracker="bytetrack.yaml", verbose=False)[0]
    out = []
    if r.boxes.id is None:
        return out
    for box, tid, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.id.tolist(),
                              r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        out.append({"track_id": int(tid), "box": tuple(int(v) for v in box),
                    "confidence": float(p), "class_name": model.names[int(c)]})
    return out


def baria_baggage(sample_fps: float = 5.0) -> None:
    from ultralytics import YOLO

    repo = REF / "baria-cctv"
    sys.path.insert(0, str(repo))
    from features.abandoned_object.processor import AbandonedObjectProcessor

    res = {"name": "baria_baggage", "detector": "yolov8n.pt (COCO), as the repo uses",
           "sample_fps": sample_fps, "clips": {}}
    n, infer_s = 0, 0.0
    for clip in clips("baggage", "normal"):
        model = YOLO("yolov8n.pt")
        proc = AbandonedObjectProcessor()
        events, bag_frames, total = [], 0, 0
        for idx, t, frame in frames(clip, sample_fps, max_seconds=None):
            t0 = time.perf_counter()
            tr = _track(model, frame, [0, 24, 26, 28])
            persons = [d for d in tr if d["class_name"] == "person"]
            objs = [d for d in tr if d["class_name"] != "person"]
            out = proc.update(objs, persons, current_time=t, frame_shape=frame.shape[:2])
            infer_s += time.perf_counter() - t0
            n += 1
            total += 1
            bag_frames += bool(objs)
            for e in out["new_events"]:
                events.append({"t": round(t, 2), "event": str(getattr(e, "event_type", type(e).__name__)),
                               "severity": str(getattr(e, "severity", ""))})
        res["clips"][clip.parent.name + "/" + clip.name] = {
            "events": events, "frames": total, "frames_with_bag": bag_frames}
        print(clip.name, len(events), "events; bag frames", bag_frames, "/", total)
    res["pipeline_fps"] = round(n / infer_s, 2)
    res["rss_mb"] = round(rss_mb())
    save("baria_baggage", res)


def baria_crowd(sample_fps: float = 5.0) -> None:
    from ultralytics import YOLO

    repo = REF / "baria-cctv"
    sys.path.insert(0, str(repo))
    from features.crowd_detection.processor import CrowdDetector

    labels = json.loads((BENCH / "crowd" / "umn_labels.json").read_text())
    res = {"name": "baria_crowd", "detector": "yolov8n.pt (COCO)", "sample_fps": sample_fps,
           "rule": "person count > 10 sustained 3 s (repo defaults)", "series": []}
    model = YOLO("yolov8n.pt")
    det = CrowdDetector()
    for idx, t, frame in frames(BENCH / "crowd" / "umn_all.avi", sample_fps, max_seconds=None):
        frame[:24] = 0  # hide the dataset's burnt-in "Abnormal Crowd Activity" caption
        r = model.predict(frame, classes=[0], conf=0.35, imgsz=640, verbose=False)[0]
        count = len(r.boxes)
        det.update(count, current_time=t)
        res["series"].append({"f": idx, "count": count, "alarm": bool(det.crowd_detected),
                              "gt": labels["labels"][idx]})
    res["rss_mb"] = round(rss_mb())
    save("baria_crowd", res)


# ---------------------------------------------------------------- saadkhan: OpenVINO anomaly rules
def saadkhan(sample_fps: float = 5.0) -> None:
    repo = REF / "saadkhan-anomaly"
    os.chdir(repo)
    sys.path.insert(0, str(repo))
    from src.detection.yolo_detector import YOLOAnomalyDetector

    labels = json.loads((BENCH / "crowd" / "umn_labels.json").read_text())
    det = YOLOAnomalyDetector(model_size="s", device="cpu")
    res = {"name": "saadkhan", "sample_fps": sample_fps, "umn": [], "normal": {}}
    n, infer_s = 0, 0.0

    def flags(r: dict) -> dict:
        return {k: v for k, v in r.items()
                if isinstance(v, (bool, int, float, str)) or k in {"anomaly_types", "alerts"}}

    for idx, t, frame in frames(BENCH / "crowd" / "umn_all.avi", sample_fps, max_seconds=None):
        frame[:24] = 0
        t0 = time.perf_counter()
        _, r = det.process_frame(frame, draw_detections=False, fps=sample_fps, timestamp=t)
        infer_s += time.perf_counter() - t0
        n += 1
        res["umn"].append({"f": idx, "gt": labels["labels"][idx], **flags(r)})
    for clip in clips("normal"):
        det.reset_tracking()
        rows = []
        for idx, t, frame in frames(clip, sample_fps):
            _, r = det.process_frame(frame, draw_detections=False, fps=sample_fps, timestamp=t)
            rows.append({"f": idx, **flags(r)})
        res["normal"][clip.name] = rows
    res["pipeline_fps"] = round(n / infer_s, 2)
    res["rss_mb"] = round(rss_mb())
    save("saadkhan", res)


# ---------------------------------------------------------------- bag detectors on ABODA
def bag_detectors(sample_fps: float = 2.0) -> None:
    from ultralytics import YOLO

    cands = {
        "theromanfour_korzo_yolov8s": (str(REF / "theromanfour-luggage" / "korzo_model.pt"), None),
        "coco_yolo11n": ("yolo11n.pt", [24, 26, 28]),
        "coco_yolo11s": ("yolo11s.pt", [24, 26, 28]),
    }
    res = {"name": "bag_detectors", "sample_fps": sample_fps, "note":
           "ABODA has no box labels; this counts sampled frames with at least one bag-class box",
           "models": {}}
    for name, (w, classes) in cands.items():
        model = YOLO(w)
        person_like = {i for i, v in model.names.items() if "person" in v.lower()}
        per_clip, n, infer_s = {}, 0, 0.0
        for clip in clips("baggage"):
            hit, tot, confs = 0, 0, []
            for idx, t, frame in frames(clip, sample_fps, max_seconds=None):
                t0 = time.perf_counter()
                r = model.predict(frame, classes=classes, conf=0.25, imgsz=640, verbose=False)[0]
                infer_s += time.perf_counter() - t0
                n += 1
                tot += 1
                bags = [p for c, p in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist())
                        if int(c) not in person_like]
                if bags:
                    hit += 1
                    confs.append(max(bags))
            per_clip[clip.name] = {"frames": tot, "frames_with_bag": hit,
                                   "mean_conf": round(sum(confs) / len(confs), 3) if confs else None}
            print(name, clip.name, hit, "/", tot)
        res["models"][name] = {"classes": model.names if classes is None else
                               {c: model.names[c] for c in classes},
                               "clips": per_clip, "infer_fps": round(n / infer_s, 2),
                               "rss_mb": round(rss_mb())}
    save("bag_detectors", res)


if __name__ == "__main__":
    task = sys.argv[1]
    if task == "accident_weights":
        # the x-size model is sampled at 1 fps so the run fits the time box on this CPU
        accident_weights(sys.argv[2], sys.argv[3], 1.0 if "11x" in sys.argv[2] else 2.0,
                         int(sys.argv[4]) if len(sys.argv) > 4 else 640)
    else:
        globals()[task]()
