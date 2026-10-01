"""Training and evaluation for training/accident_event_model.py (see its docstring)."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results"
MODELS = ROOT / "models"
FPS = 4.0
WIN = 12
SEED = 20261001


def label_at(meta: dict, t: float) -> int | None:
    if meta["kind"] == "normal":
        return 0
    if meta["kind"] == "untimed":
        return None  # contains an accident at an unknown time: no frame labels
    for a, b in meta["spans"]:
        if a <= t <= b:
            return 1
    if any(a - 2 <= t < a for a, _ in meta["spans"]):
        return None
    if all(t < a - 2 for a, _ in meta["spans"]):
        return 0
    return None  # aftermath


def windows(vids: dict, key, split: str, views=("clean",)):
    X, y, g, tt = [], [], [], []
    for v, meta in vids.items():
        if meta["split"] != split or not key(v).exists():
            continue
        d = np.load(key(v))
        t = d["t"]
        for view in views:
            if view not in d.files:
                continue
            e = d[view].astype(np.float32)
            for i in range(WIN - 1, len(t)):
                lab = label_at(meta, float(t[i]))
                if lab is None:
                    continue
                X.append(e[i - WIN + 1:i + 1])
                y.append(lab)
                g.append(v)
                tt.append(float(t[i]))
    if not X:
        return np.zeros((0, WIN, 576), np.float32), np.zeros(0), np.array([]), np.zeros(0)
    return np.stack(X), np.array(y), np.array(g), np.array(tt)


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s)
    if len(set(y.tolist())) < 2:
        return None
    order = np.argsort(s)
    r = np.empty(len(s))
    r[order] = np.arange(1, len(s) + 1)
    pos = y == 1
    return float((r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def score_video(meta: dict, t: np.ndarray, p: np.ndarray, thr: float) -> dict:
    """Alarm = 2 consecutive windows over thr. Hit if it starts 1 s before onset .. end of span."""
    starts = [float(t[i]) for i in range(1, len(p)) if p[i] >= thr and p[i - 1] >= thr and (i < 2 or p[i - 2] < thr)]
    dur = float(t[-1] - t[0]) if len(t) else 0.0
    if meta["kind"] == "accident":
        a, b = meta["spans"][0]
        hits = [s for s in starts if a - 1 <= s <= b]
        return {"caught": bool(hits), "delay_s": round(hits[0] - a, 1) if hits else None,
                "early": sum(1 for s in starts if s < a - 1), "seconds": dur}
    if meta["kind"] == "untimed":
        return {"caught": bool(starts), "seconds": dur}
    return {"false_alarms": len(starts), "seconds": dur}


def video_probs(vids, key, predict, split):
    out = {}
    for v, meta in vids.items():
        if meta["split"] != split or not key(v).exists():
            continue
        d = np.load(key(v))
        e = d["clean"].astype(np.float32)
        if len(e) < WIN:
            continue
        W = np.stack([e[i - WIN + 1:i + 1] for i in range(WIN - 1, len(e))])
        out[v] = (d["t"][WIN - 1:], predict(W))
    return out


def summarise(vids, probs, thr) -> dict:
    rows = {v: score_video(vids[v], t, p, thr) for v, (t, p) in probs.items()}
    acc = [r for v, r in rows.items() if vids[v]["kind"] == "accident"]
    unt = [r for v, r in rows.items() if vids[v]["kind"] == "untimed"]
    nor = [r for v, r in rows.items() if vids[v]["kind"] == "normal"]
    hours = sum(r["seconds"] for r in nor) / 3600
    delays = sorted(r["delay_s"] for r in acc if r["delay_s"] is not None)
    fa = sum(r["false_alarms"] for r in nor)
    return {"accident_videos": len(acc), "caught": sum(r["caught"] for r in acc),
            "recall": round(sum(r["caught"] for r in acc) / len(acc), 3) if acc else None,
            "median_delay_s": delays[len(delays) // 2] if delays else None,
            "early_alarms": sum(r["early"] for r in acc),
            "untimed_accident_videos": len(unt), "untimed_flagged": sum(r["caught"] for r in unt),
            "normal_videos": len(nor), "normal_hours": round(hours, 3), "false_alarms": fa,
            "false_alarms_per_camera_hour": round(fa / hours, 1) if hours else None}


def pick_threshold(vids, probs) -> float:
    best = (-1e9, 0.5)
    for thr in np.arange(0.3, 0.96, 0.05):
        s = summarise(vids, probs, thr)
        score = (s["caught"] or 0) - 0.25 * (s["false_alarms"] or 0) - 0.25 * (s["early_alarms"] or 0)
        if score > best[0]:
            best = (score, round(float(thr), 2))
    return best[1]


def train(vids: dict, key) -> None:
    import torch
    from sklearn.linear_model import LogisticRegression

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    Xtr, ytr, gtr, _ = windows(vids, key, "train", views=("clean", "aug0", "aug1"))
    Xva, yva, _, _ = windows(vids, key, "val")
    Xte, yte, _, _ = windows(vids, key, "test")
    print(f"windows: train {len(ytr)} ({int(ytr.sum())} pos), val {len(yva)} ({int(yva.sum())} pos), "
          f"test {len(yte)} ({int(yte.sum())} pos)", flush=True)
    mu = Xtr.reshape(-1, Xtr.shape[-1]).mean(0)
    sd = Xtr.reshape(-1, Xtr.shape[-1]).std(0) + 1e-5

    # --- baseline: logistic regression on the mean-pooled window
    lr = LogisticRegression(C=0.1, class_weight="balanced", max_iter=3000).fit(((Xtr - mu) / sd).mean(1), ytr)

    def lr_predict(W):
        return lr.predict_proba(((W - mu) / sd).mean(1))[:, 1]

    # --- temporal head: GRU
    class Head(torch.nn.Module):
        def __init__(self, d: int):
            super().__init__()
            self.gru = torch.nn.GRU(d, 64, batch_first=True)
            self.drop = torch.nn.Dropout(0.3)
            self.out = torch.nn.Linear(64, 1)

        def forward(self, x):
            h, _ = self.gru(x)
            return self.out(self.drop(h[:, -1]))

    net = Head(Xtr.shape[-1])
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-3)
    pos_w = torch.tensor([(1 - ytr.mean()) / max(ytr.mean(), 1e-6)], dtype=torch.float32)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_w)
    xt = torch.from_numpy(((Xtr - mu) / sd).astype(np.float32))
    yt = torch.from_numpy(ytr.astype(np.float32))[:, None]
    xv = torch.from_numpy(((Xva - mu) / sd).astype(np.float32))
    best_state, best_auc, t0 = None, -1.0, time.time()
    for epoch in range(25):
        net.train()
        perm = torch.randperm(len(xt))
        for i in range(0, len(xt), 256):
            b = perm[i:i + 256]
            opt.zero_grad()
            loss_fn(net(xt[b]), yt[b]).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            pv = torch.sigmoid(net(xv))[:, 0].numpy()
        a = auc(yva, pv) or 0.0
        if a > best_auc:  # early stopping on val window AUC
            best_auc, best_state = a, {k: v.clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state)
    net.eval()

    def gru_predict(W):
        with torch.no_grad():
            return torch.sigmoid(net(torch.from_numpy(((W - mu) / sd).astype(np.float32))))[:, 0].numpy()

    results = {}
    for name, pred in (("gru", gru_predict), ("mean_pool_logreg", lr_predict)):
        pv = video_probs(vids, key, pred, "val")
        thr = pick_threshold(vids, pv)
        pt = video_probs(vids, key, pred, "test")
        te_p = pred(Xte) if len(Xte) else np.zeros(0)
        results[name] = {"threshold_chosen_on_val": thr, "val_window_auc": round(auc(yva, pred(Xva)) or 0, 4),
                         "test_window_auc": round(auc(yte, te_p) or 0, 4) if len(te_p) else None,
                         "val_events": summarise(vids, pv, thr), "test_events": summarise(vids, pt, thr)}
    winner = max(results, key=lambda k: (results[k]["test_events"]["caught"] or 0) * 0 + (results[k]["val_window_auc"]))
    # the winner is picked on val, never on test
    winner = max(results, key=lambda k: results[k]["val_window_auc"])

    # our own videos: leave-one-video-out with the winning recipe
    own = [v for v in vids if "data/custom/" in v and key(v).exists()]
    lovo = {}
    for v in own:
        keep = gtr != v
        m2 = LogisticRegression(C=0.1, class_weight="balanced", max_iter=3000).fit(((Xtr[keep] - mu) / sd).mean(1), ytr[keep])
        pr = video_probs({v: vids[v]}, key, lambda W: m2.predict_proba(((W - mu) / sd).mean(1))[:, 1], vids[v]["split"])
        if v in pr:
            t, p = pr[v]
            lovo[v] = score_video(vids[v], t, p, results["mean_pool_logreg"]["threshold_chosen_on_val"])

    # speed of the whole event model on this machine (encoder + head, one frame)
    from accident_event_model import encoder
    enc = encoder()
    frame = (np.random.rand(480, 640, 3) * 255).astype(np.uint8)
    enc([frame])
    t1 = time.perf_counter()
    for _ in range(20):
        enc([frame])
    enc_ms = (time.perf_counter() - t1) / 20 * 1000
    W1 = Xte[:1] if len(Xte) else np.zeros((1, WIN, 576), np.float32)
    t1 = time.perf_counter()
    for _ in range(50):
        gru_predict(W1)
    head_ms = (time.perf_counter() - t1) / 50 * 1000

    counts = {s: sum(1 for v in vids.values() if v["split"] == s and key_exists(key, vids, v))
              for s in ("train", "val", "test")}
    res = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "encoder": "MobileNetV3-Small (ImageNet), frozen, 576-d, 4 fps", "window_s": WIN / FPS,
        "data": "data/labels/accident_events.csv (UCF-Crime RoadAccidents + Normal, TADBench with NVIDIA "
                "timestamps, team videos); frozen video-level split",
        "videos_embedded_by_split": counts,
        "windows": {"train_incl_2_augmented_views": int(len(ytr)), "val": int(len(yva)), "test": int(len(yte))},
        "models": results, "winner_on_val": winner,
        "team_videos_leave_one_out": lovo,
        "speed_ms_per_frame": {"encoder": round(enc_ms, 1), "gru_head_per_window": round(head_ms, 2)},
    }
    (RESULTS / "accident_event.json").write_text(json.dumps(res, indent=1))
    torch.save({"state": net.state_dict(), "mu": mu.tolist(), "sd": sd.tolist(), "win": WIN, "fps": FPS,
                "threshold": results["gru"]["threshold_chosen_on_val"]}, MODELS / "accident_event.pt")
    try:
        torch.onnx.export(net, torch.zeros(1, WIN, Xtr.shape[-1]), str(MODELS / "accident_event.onnx"),
                          input_names=["window"], output_names=["logit"], dynamic_axes={"window": {0: "n"}})
    except Exception as e:  # noqa: BLE001
        res["onnx_export_error"] = repr(e)
        (RESULTS / "accident_event.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "models"}, indent=1))
    for k, v in results.items():
        print(k, json.dumps(v))


def key_exists(key, vids, v) -> bool:
    for name, meta in vids.items():
        if meta is v:
            return key(name).exists()
    return False
