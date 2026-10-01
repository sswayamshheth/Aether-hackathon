"""Phase C, crowd: multi-class crowd behaviour from grid motion features.

    backend\\.venv\\Scripts\\python training\\crowd_event_model.py features   (resumable)
    backend\\.venv\\Scripts\\python training\\crowd_event_model.py train

Classes   normal, panic, fight, congestion, obstacle (MED labels, plus UMN panic, plus
          UCSD Ped2 non-pedestrian entities mapped to "obstacle")
Features  per frame at 5 fps, on a 3x3 grid: Farneback optical-flow magnitude, divergence,
          direction entropy, and foreground share (frame difference); plus whole-frame p95
          flow. 37 numbers a frame. Normalised per camera: each video's features are divided
          by their median over its first 10 s, the way a live camera would calibrate on its
          own normal footage (MED and UMN clips all start normal). Rates of change are the
          window-level "last minus first" statistics.
Windows   2 s (10 frames). MED videos start normal and end abnormal, so windows are drawn
          from every part of every video and each class is capped per video, so the model
          cannot learn "late in the clip = abnormal".
Models    (a) HistGradientBoosting on window statistics (mean, max, std, last-first);
          (b) GRU over the 10 frames. Picked on grouped cross-validation over the training
          videos (a video is never in train and test at once), then scored once on the
          frozen test split.
Writes    models/crowd_event.json (+ .pkl for boosting / .pt for GRU),
          docs/results/crowd_event.json, a row in EXPERIMENTS.md
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FEAT = ROOT / "data" / "cache" / "crowd_grid"
FEAT.mkdir(parents=True, exist_ok=True)
LABELS = ROOT / "data" / "labels" / "crowd_events.csv"
RESULTS = ROOT / "docs" / "results"
MODELS = ROOT / "models"
FPS = 5.0
WIN = 10
CLASSES = ["normal", "panic", "fight", "congestion", "obstacle"]
MAP = {"non_pedestrian": "obstacle"}
SEED = 20261001
SIZE = (192, 144)


def key(v: str) -> Path:
    return FEAT / (hashlib.sha1(v.encode("utf-8")).hexdigest()[:16] + ".npz")


def load() -> dict[str, dict]:
    vids: dict[str, dict] = {}
    with LABELS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = vids.setdefault(r["video_path"], {"split": r["split"], "spans": [], "source": r["source"]})
            ev = MAP.get(r["event_type"], r["event_type"])
            if ev in CLASSES:
                v["spans"].append((float(r["start_s"]), float(r["end_s"]), ev))
    return vids


def frames(v: str):
    path, _, rng = v.partition("#")
    cap = cv2.VideoCapture(str(ROOT / path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    lo, hi = (int(x) for x in rng.split("-")) if rng else (0, 10**9)
    if lo:
        cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
    i, nxt = lo, float(lo)
    step = fps / FPS
    while i <= hi and cap.grab():
        if i >= nxt:
            ok, img = cap.retrieve()
            if ok:
                yield i / fps, img
            nxt += step
        i += 1
    cap.release()


def frame_features(prev: np.ndarray, cur: np.ndarray) -> np.ndarray:
    flow = cv2.calcOpticalFlowFarneback(prev, cur, None, 0.5, 2, 11, 2, 5, 1.1, 0)
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    div = np.gradient(flow[..., 0], axis=1) + np.gradient(flow[..., 1], axis=0)
    fg = (cv2.absdiff(prev, cur) > 18).astype(np.float32)
    h, w = cur.shape
    out = []
    for gy in range(3):
        for gx in range(3):
            sl = (slice(gy * h // 3, (gy + 1) * h // 3), slice(gx * w // 3, (gx + 1) * w // 3))
            m, a = mag[sl], ang[sl]
            mv = m > 0.3
            if mv.sum() > 10:
                hist, _ = np.histogram(a[mv], bins=8, range=(0, 2 * np.pi), weights=m[mv])
                p = hist / (hist.sum() + 1e-9)
                ent = float(-(p * np.log(p + 1e-9)).sum() / np.log(8))
            else:
                ent = 0.0
            out += [float(m.mean()), float(div[sl].mean()), ent, float(fg[sl].mean())]
    out.append(float(np.percentile(mag, 95)))
    return np.array(out, dtype=np.float32)


def extract() -> None:
    vids = load()
    todo = [v for v in vids if not key(v).exists()]
    for k, v in enumerate(todo):
        t0 = time.time()
        ts, feats, prev = [], [], None
        for t, img in frames(v):
            g = cv2.cvtColor(cv2.resize(img, SIZE), cv2.COLOR_BGR2GRAY)
            g[: int(SIZE[1] * 24 / 240)] = 0 if "umn" in v else g[: int(SIZE[1] * 24 / 240)]  # UMN caption
            if prev is not None:
                ts.append(t)
                feats.append(frame_features(prev, g))
            prev = g
        if feats:
            np.savez(key(v), t=np.array(ts, np.float32), f=np.stack(feats))
        print(f"[{k + 1}/{len(todo)}] {v}: {len(ts)} frames {time.time() - t0:.0f}s", flush=True)


def normalise(t: np.ndarray, f: np.ndarray) -> np.ndarray:
    base = f[t <= t[0] + 10.0]
    scale = np.median(np.abs(base), axis=0) + 1e-3
    return f / scale


def label_at(meta: dict, t: float) -> str | None:
    for a, b, ev in meta["spans"]:
        if a <= t <= b:
            return ev
    return None


def windows(vids: dict, split: str, cap_per_class: int = 60, seed: int = SEED):
    rng = np.random.default_rng(seed)
    X, y, g = [], [], []
    for v, meta in vids.items():
        if meta["split"] != split or not key(v).exists():
            continue
        d = np.load(key(v))
        t, f = d["t"], normalise(d["t"], d["f"])
        per: dict[str, list] = {}
        for i in range(WIN - 1, len(t)):
            lab = label_at(meta, float(t[i]))
            if lab is not None and label_at(meta, float(t[i - WIN + 1])) == lab:  # window inside one label
                per.setdefault(lab, []).append(i)
        for lab, idx in per.items():
            if split == "train" and len(idx) > cap_per_class:
                idx = sorted(rng.choice(idx, cap_per_class, replace=False))
            for i in idx:
                X.append(f[i - WIN + 1:i + 1])
                y.append(CLASSES.index(lab))
                g.append(v)
    return np.stack(X), np.array(y), np.array(g)


def stats(X: np.ndarray) -> np.ndarray:
    return np.concatenate([X.mean(1), X.max(1), X.std(1), X[:, -1] - X[:, 0]], axis=1)


def metrics(y, pred, proba) -> dict:
    from sklearn.metrics import f1_score, roc_auc_score

    out = {"macro_f1": round(float(f1_score(y, pred, average="macro", labels=range(len(CLASSES)), zero_division=0)), 4),
           "per_class_f1": {c: round(float(x), 3) for c, x in
                            zip(CLASSES, f1_score(y, pred, average=None, labels=range(len(CLASSES)), zero_division=0))}}
    ab = (y != 0).astype(int)  # abnormal vs normal, the question the dashboard asks
    if len(set(ab)) > 1:
        out["abnormal_vs_normal_auc"] = round(float(roc_auc_score(ab, 1 - proba[:, 0])), 4)
    out["windows"] = int(len(y))
    out["windows_per_class"] = {c: int((y == i).sum()) for i, c in enumerate(CLASSES)}
    return out


def train() -> None:
    import torch
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold

    torch.manual_seed(SEED)
    vids = load()
    Xtr, ytr, gtr = windows(vids, "train")
    Xte, yte, gte = windows(vids, "test")
    Xva, yva, gva = windows(vids, "val")
    Xtv, ytv, gtv = np.concatenate([Xtr, Xva]), np.concatenate([ytr, yva]), np.concatenate([gtr, gva])
    print(f"windows: train+val {len(ytv)} {np.bincount(ytv, minlength=5)}, test {len(yte)} {np.bincount(yte, minlength=5)}")

    def fit_hgb(X, y):
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, class_weight="balanced",
                                              random_state=SEED).fit(stats(X), y)

    class GRU(torch.nn.Module):
        def __init__(self, d):
            super().__init__()
            self.gru = torch.nn.GRU(d, 48, batch_first=True)
            self.out = torch.nn.Linear(48, len(CLASSES))

        def forward(self, x):
            h, _ = self.gru(x)
            return self.out(h[:, -1])

    def fit_gru(X, y):
        mu, sd = X.reshape(-1, X.shape[-1]).mean(0), X.reshape(-1, X.shape[-1]).std(0) + 1e-5
        net = GRU(X.shape[-1])
        opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-3)
        w = torch.tensor(len(y) / (len(CLASSES) * np.maximum(np.bincount(y, minlength=len(CLASSES)), 1)),
                         dtype=torch.float32)
        lf = torch.nn.CrossEntropyLoss(weight=w)
        xt, yt = torch.from_numpy(((X - mu) / sd).astype(np.float32)), torch.from_numpy(y.astype(np.int64))
        for _ in range(30):
            perm = torch.randperm(len(xt))
            for i in range(0, len(xt), 128):
                b = perm[i:i + 128]
                opt.zero_grad()
                lf(net(xt[b]), yt[b]).backward()
                opt.step()
        net.eval()

        class M:
            def predict_proba(self, Xn):
                with torch.no_grad():
                    return torch.softmax(net(torch.from_numpy(((Xn - mu) / sd).astype(np.float32))), -1).numpy()
        M.net, M.mu, M.sd = net, mu, sd
        return M()

    # model selection: grouped 5-fold CV over train+val videos (never touches test)
    cv = {"hgb": [], "gru": []}
    for tr, te in GroupKFold(n_splits=5).split(Xtv, ytv, gtv):
        h = fit_hgb(Xtv[tr], ytv[tr])
        p = h.predict_proba(stats(Xtv[te]))
        cv["hgb"].append(metrics(ytv[te], p.argmax(1), p)["macro_f1"])
        m = fit_gru(Xtv[tr], ytv[tr])
        p = m.predict_proba(Xtv[te])
        cv["gru"].append(metrics(ytv[te], p.argmax(1), p)["macro_f1"])
    cv_mean = {k: round(float(np.mean(v)), 4) for k, v in cv.items()}
    winner = max(cv_mean, key=cv_mean.get)
    final = fit_hgb(Xtv, ytv) if winner == "hgb" else fit_gru(Xtv, ytv)
    p_te = final.predict_proba(stats(Xte) if winner == "hgb" else Xte)
    test = metrics(yte, p_te.argmax(1), p_te)
    other = fit_gru(Xtv, ytv) if winner == "hgb" else fit_hgb(Xtv, ytv)
    p_o = other.predict_proba(Xte if winner == "hgb" else stats(Xte))
    test_other = metrics(yte, p_o.argmax(1), p_o)

    # per-source test breakdown (abnormal vs normal AUC)
    from sklearn.metrics import roc_auc_score
    by_src = {}
    for src in sorted({vids[v]["source"] for v in set(gte)}):
        m = np.array([vids[v]["source"] == src for v in gte])
        ab = (yte[m] != 0).astype(int)
        if m.sum() and len(set(ab)) > 1:
            by_src[src] = {"windows": int(m.sum()), "abnormal_vs_normal_auc": round(float(roc_auc_score(ab, 1 - p_te[m, 0])), 4)}

    t0 = time.perf_counter()
    for _ in range(50):
        final.predict_proba(stats(Xte[:1]) if winner == "hgb" else Xte[:1])
    ms = (time.perf_counter() - t0) / 50 * 1000
    res = {"created": datetime.now().isoformat(timespec="seconds"), "classes": CLASSES,
           "data": "data/labels/crowd_events.csv (MED, UMN, UCSD Ped2); frozen video-level split",
           "videos": {s: len({v for v, m in vids.items() if m["split"] == s and key(v).exists()})
                      for s in ("train", "val", "test")},
           "features": "3x3 grid flow magnitude, divergence, direction entropy, foreground share + p95 flow; "
                       "5 fps; per-video normalisation on its first 10 s; 2 s windows",
           "cv_macro_f1_grouped_by_video": cv_mean, "winner": winner, "test": test,
           "test_other_model": {"model": "gru" if winner == "hgb" else "hgb", **test_other},
           "test_by_source": by_src, "head_ms_per_window": round(ms, 2)}
    (RESULTS / "crowd_event.json").write_text(json.dumps(res, indent=1))
    if winner == "hgb":
        import pickle
        (MODELS / "crowd_event_hgb.pkl").write_bytes(pickle.dumps(final))
    else:
        torch.save({"state": final.net.state_dict(), "mu": final.mu.tolist(), "sd": final.sd.tolist()},
                   MODELS / "crowd_event_gru.pt")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    extract() if sys.argv[1] == "features" else train()
