"""Train the crowd-anomaly temporal CNN on UMN and report frame-level AUC on held-out scenes.

Features come from our own pipeline (same detector, tracker and CrowdFeatures class used
live), sampled at 10 fps, with the dataset's burnt-in caption masked out.

Split is by scene, never by frame: scenes 1, 4, 7, 9 (one lawn, two indoor, one plaza)
are held out and never seen in training.

    backend\\.venv\\Scripts\\python training\\train_crowd.py
Writes models/crowd_tcn.pt and docs/results/crowd_model.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "models")

from app import config  # noqa: E402
from app.detector import Tracker, get_detector  # noqa: E402
from app.engines.crowd import FEATURES, WINDOW, CrowdFeatures, build_tcn  # noqa: E402

CROWD = ROOT / "data" / "bench" / "crowd"
FEAT_FILE = CROWD / "umn_features.npz"
TEST_SCENES = [1, 4, 7, 9]
STEP = 3  # 30 fps source -> 10 fps
MASK_ROWS = 24


def extract() -> None:
    labels = json.loads((CROWD / "umn_labels.json").read_text())
    det = get_detector()
    cap = cv2.VideoCapture(str(CROWD / "umn_all.avi"))
    rows = []
    scene_of = np.zeros(labels["frames"], dtype=int)
    for si, s in enumerate(labels["scenes"]):
        scene_of[s["start"]:s["end"] + 1] = si
    feat, tracker, cur_scene, idx, n_det = CrowdFeatures(), Tracker(5), -1, -1, 0
    persons: list = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        idx += 1
        if idx % STEP or idx >= labels["frames"]:
            continue
        sc = int(scene_of[idx])
        if sc != cur_scene:  # new scene: fresh tracker and flow state
            feat, tracker, cur_scene, n_det = CrowdFeatures(), Tracker(5), sc, 0
        img[:MASK_ROWS] = 0
        if n_det % config.DETECT_EVERY == 0:
            persons = [t for t in tracker.update(det.detect(img), img) if t.cls == "person"]
        n_det += 1
        x = feat.step(img, idx / 30.0, persons)
        if x is not None:
            rows.append((idx, sc, labels["labels"][idx], *x))
        if len(rows) % 500 == 0:
            print(len(rows), "feature rows")
    arr = np.array(rows, dtype=np.float32)
    np.savez(FEAT_FILE, data=arr)
    print("saved", arr.shape)


def windows(arr: np.ndarray, scenes: list[int]):
    xs, ys, fr = [], [], []
    for sc in scenes:
        part = arr[arr[:, 1] == sc]
        for i in range(WINDOW, len(part) + 1):
            xs.append(part[i - WINDOW:i, 3:])
            ys.append(part[i - 1, 2])
            fr.append(part[i - 1, 0])
    return np.stack(xs), np.array(ys), np.array(fr)


def auc(y: np.ndarray, s: np.ndarray) -> float:
    order = np.argsort(s)
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    for v in np.unique(s):  # average ranks over ties
        m = s == v
        ranks[m] = ranks[m].mean()
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def train() -> None:
    import torch

    torch.manual_seed(7)
    np.random.seed(7)
    arr = np.load(FEAT_FILE)["data"]
    all_scenes = sorted(int(s) for s in set(arr[:, 1].astype(int)))
    train_scenes = [s for s in all_scenes if s not in TEST_SCENES]
    xtr, ytr, _ = windows(arr, train_scenes)
    xte, yte, _ = windows(arr, TEST_SCENES)
    mean = xtr.reshape(-1, xtr.shape[-1]).mean(0)
    std = xtr.reshape(-1, xtr.shape[-1]).std(0) + 1e-6

    def prep(x):
        return torch.from_numpy(((x - mean) / std).transpose(0, 2, 1).astype(np.float32))

    net = build_tcn()
    opt = torch.optim.Adam(net.parameters(), lr=2e-3, weight_decay=1e-4)
    pos_w = torch.tensor([(1 - ytr.mean()) / max(ytr.mean(), 1e-6)], dtype=torch.float32)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_w)
    xt, yt = prep(xtr), torch.from_numpy(ytr.astype(np.float32))[:, None]
    for epoch in range(40):
        net.train()
        perm = torch.randperm(len(xt))
        tot = 0.0
        for i in range(0, len(xt), 64):
            b = perm[i:i + 64]
            opt.zero_grad()
            loss = loss_fn(net(xt[b]), yt[b])
            loss.backward()
            opt.step()
            tot += float(loss) * len(b)
        if epoch % 10 == 9:
            print(f"epoch {epoch + 1} loss {tot / len(xt):.4f}")
    net.eval()
    with torch.no_grad():
        p_te = torch.sigmoid(net(prep(xte)))[:, 0].numpy()
        p_tr = torch.sigmoid(net(prep(xtr)))[:, 0].numpy()
    pred = p_te >= 0.5
    tp, fp = int((pred & (yte == 1)).sum()), int((pred & (yte == 0)).sum())
    fn = int((~pred & (yte == 1)).sum())
    res = {
        "model": "temporal CNN (2 x Conv1d, 24 channels) over a 1.6 s window of 8 per-frame features",
        "features": FEATURES, "dataset": "UMN Unusual Crowd Activity (University of Minnesota)",
        "sampling": "10 fps, caption rows masked", "split": "by scene",
        "train_scenes": train_scenes, "test_scenes": TEST_SCENES,
        "train_windows": int(len(ytr)), "test_windows": int(len(yte)),
        "test_abnormal_windows": int(yte.sum()),
        "frame_auc_test": round(auc(yte, p_te), 4), "frame_auc_train": round(auc(ytr, p_tr), 4),
        "baseline_auc_test_flow_mean_only": round(auc(yte, xte[:, -1, FEATURES.index("flow_mean")]), 4),
        "baseline_auc_test_speed_max_only": round(auc(yte, xte[:, -1, FEATURES.index("speed_max")]), 4),
        "precision_at_0.5": round(tp / max(tp + fp, 1), 3), "recall_at_0.5": round(tp / max(tp + fn, 1), 3),
        "note": "UMN is staged (people told to run). Expect weaker numbers on real CCTV.",
    }
    torch.save({"state": net.state_dict(), "mean": mean.tolist(), "std": std.tolist(),
                "features": FEATURES, "window": WINDOW}, ROOT / "models" / "crowd_tcn.pt")
    (ROOT / "docs" / "results" / "crowd_model.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    if not FEAT_FILE.exists() or "--extract" in sys.argv:
        extract()
    train()
