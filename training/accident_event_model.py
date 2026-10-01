"""Phase C, accident: frozen lightweight image encoder + small temporal head.

    backend\\.venv\\Scripts\\python training\\accident_event_model.py embed   (slow, resumable)
    backend\\.venv\\Scripts\\python training\\accident_event_model.py train

Encoder   torchvision MobileNetV3-Small, ImageNet weights, frozen; 576-d pooled features at
          4 fps. Chosen because it runs in real time on a laptop CPU.
Augment   training videos are embedded twice more with CCTV-style degradation: JPEG
          re-compression, blur, sensor noise and low light (fixed random seed).
Head      GRU over 12 frames (3 s) -> P(accident). A window is positive when its last frame
          lies inside a labelled accident interval, negative when it lies in a normal video
          or more than 2 s before an accident, and dropped otherwise (aftermath).
Baseline  logistic regression on the mean-pooled window (no temporal model), same data.
Splits    the frozen video-level split in data/labels/splits.json. Choices are made on val;
          test is scored once at the end.
Metrics   window AUC; event recall and detection delay on test accident videos; false alarms
          per camera-hour on test normal videos.
Writes    models/accident_event.pt, models/accident_event.onnx,
          docs/results/accident_event.json, a row in EXPERIMENTS.md
"""
from __future__ import annotations

import csv
import hashlib
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "training"))
os.environ.setdefault("TORCH_HOME", str(ROOT / ".cache" / "torch"))

EMB = ROOT / "data" / "cache" / "acc_mnv3"
EMB.mkdir(parents=True, exist_ok=True)
LABELS = ROOT / "data" / "labels" / "accident_events.csv"
FPS = 4.0
WIN = 12
SEED = 20261001


def key(v: str) -> Path:
    """Stable cache file per video (Python's hash() changes between runs)."""
    return EMB / (hashlib.sha1(v.encode("utf-8")).hexdigest()[:16] + ".npz")


def load_events() -> dict[str, dict]:
    vids: dict[str, dict] = {}
    with LABELS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = vids.setdefault(r["video_path"], {"split": r["split"], "spans": [], "kind": "normal",
                                                  "source": r["source"]})
            if r["event_type"] == "accident":
                v["spans"].append((float(r["start_s"]), float(r["end_s"])))
                v["kind"] = "accident"
            elif r["event_type"] == "accident_untimed" and v["kind"] == "normal":
                v["kind"] = "untimed"
    return vids


def degrade(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """CCTV-style augmentation: a random mix of JPEG, blur, noise and low light."""
    out = img
    if rng.random() < 0.7:
        q = int(rng.integers(15, 45))
        out = cv2.imdecode(cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR)
    if rng.random() < 0.5:
        k = int(rng.choice([3, 5]))
        out = cv2.GaussianBlur(out, (k, k), 0)
    if rng.random() < 0.5:
        out = np.clip(out.astype(np.float32) + rng.normal(0, rng.uniform(4, 12), out.shape), 0, 255).astype(np.uint8)
    if rng.random() < 0.4:
        out = np.clip(out.astype(np.float32) * rng.uniform(0.35, 0.7), 0, 255).astype(np.uint8)
    return out


def encoder():
    import torch
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    torch.set_num_threads(max(1, (os.cpu_count() or 4) // 2))
    m = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1).eval()
    feat = torch.nn.Sequential(m.features, m.avgpool, torch.nn.Flatten())
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def run(frames: list[np.ndarray]) -> np.ndarray:
        out = []
        for i in range(0, len(frames), 32):
            x = np.stack([(cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2RGB), (224, 224)).astype(np.float32) / 255 - mean)
                          / std for f in frames[i:i + 32]]).transpose(0, 3, 1, 2)
            with torch.no_grad():
                out.append(feat(torch.from_numpy(x)).numpy().astype(np.float16))
        return np.concatenate(out)

    return run


def video_frames(path: str):
    cap = cv2.VideoCapture(str(ROOT / path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = fps / FPS
    i, nxt = 0, 0.0
    while cap.grab():
        if i >= nxt:
            ok, img = cap.retrieve()
            if ok:
                yield i / fps, img
            nxt += step
        i += 1
    cap.release()


def embed() -> None:
    vids = load_events()
    run = encoder()
    todo = [(v, m) for v, m in vids.items() if not key(v).exists()]
    # own videos and accident videos first, so a partial run is already useful
    todo.sort(key=lambda t: (0 if "custom" in t[0] else 1 if t[1]["kind"] == "accident" else 2))
    rng = np.random.default_rng(SEED)
    for k, (v, meta) in enumerate(todo):
        t0 = time.time()
        ts, frames = [], []
        for t, img in video_frames(v):
            ts.append(t)
            frames.append(img)
        if not frames:
            continue
        views = {"clean": run(frames)}
        if meta["split"] == "train":
            for a in range(2):
                views[f"aug{a}"] = run([degrade(f, rng) for f in frames])
        np.savez(key(v), t=np.array(ts, dtype=np.float32), **views)
        print(f"[{k + 1}/{len(todo)}] {v}: {len(ts)} frames, {len(views)} views, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "embed":
        embed()
    elif sys.argv[1] == "train":
        from accident_event_train import train  # noqa: E402

        train(load_events(), key)
