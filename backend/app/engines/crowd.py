"""Crowd-anomaly engine.

Learned part: a small temporal CNN over per-frame motion and occupancy features
(training/train_crowd.py, trained on UMN). Rule part on top: an overcrowding limit, and
a motion z-score fallback used only when no trained model file is present.
"""
from __future__ import annotations

import logging
import math
from collections import deque

import cv2
import numpy as np

from .. import config
from ..schema import Candidate, Frame

log = logging.getLogger("drishti.crowd")

FEATURES = ["people", "moving_frac", "flow_mean", "flow_p95", "dir_entropy",
            "speed_mean", "speed_max", "people_delta"]
WINDOW = 16
MIN_CROWD = 6  # a crowd anomaly needs a crowd: fewer people than this never raise one
FLOW_SIZE = (160, 120)


class CrowdFeatures:
    """Per-frame feature extractor. Flow is measured per second, so it does not depend on
    the frame rate the pipeline happens to reach."""

    def __init__(self) -> None:
        self.prev_gray: np.ndarray | None = None
        self.prev_ts = 0.0
        self.pos: dict[int, deque] = {}
        self.counts: deque = deque(maxlen=20)

    def reset(self) -> None:
        self.__init__()

    def step(self, image: np.ndarray, ts: float, persons: list) -> np.ndarray | None:
        gray = cv2.cvtColor(cv2.resize(image, FLOW_SIZE), cv2.COLOR_BGR2GRAY)
        prev, prev_ts = self.prev_gray, self.prev_ts
        self.prev_gray, self.prev_ts = gray, ts
        dt = ts - prev_ts
        if prev is None or dt <= 0 or dt > 1.0:
            return None
        flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 2, 9, 2, 5, 1.1, 0)
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        mag = mag / dt / FLOW_SIZE[1]  # frame-heights per second
        moving = mag > 0.04
        frac = float(moving.mean())
        if moving.sum() > 20:
            m_mean = float(mag[moving].mean())
            m_p95 = float(np.percentile(mag[moving], 95))
            hist, _ = np.histogram(ang[moving], bins=8, range=(0, 2 * math.pi), weights=mag[moving])
            p = hist / (hist.sum() + 1e-9)
            ent = float(-(p * np.log(p + 1e-9)).sum() / math.log(8))
        else:
            m_mean = m_p95 = ent = 0.0

        h = image.shape[0]
        speeds = []
        live = set()
        for t in persons:
            live.add(t.id)
            dq = self.pos.setdefault(t.id, deque(maxlen=8))
            dq.append((ts, t.center[0], t.center[1], max(t.height, 1.0)))
            if len(dq) >= 2 and dq[-1][0] - dq[0][0] > 0.2:
                d = math.hypot(dq[-1][1] - dq[0][1], dq[-1][2] - dq[0][2])
                speeds.append(d / dq[-1][3] / (dq[-1][0] - dq[0][0]))  # body-heights per second
        for tid in [k for k in self.pos if k not in live]:
            del self.pos[tid]
        n = len(persons)
        self.counts.append(n)
        delta = n - self.counts[0]
        _ = h
        return np.array([n / 20.0, frac, m_mean, m_p95, ent,
                         float(np.mean(speeds)) if speeds else 0.0,
                         float(np.max(speeds)) if speeds else 0.0, delta / 10.0], dtype=np.float32)


def build_tcn(n_features: int = len(FEATURES)):
    import torch.nn as nn

    return nn.Sequential(
        nn.Conv1d(n_features, 24, 3, padding=1), nn.ReLU(),
        nn.Conv1d(24, 24, 3, padding=2, dilation=2), nn.ReLU(),
        nn.AdaptiveMaxPool1d(1), nn.Flatten(), nn.Dropout(0.2), nn.Linear(24, 1))


class CrowdModel:
    def __init__(self) -> None:
        self.available = False
        if not config.CROWD_MODEL.exists():
            log.warning("no crowd model at %s, using the motion z-score fallback", config.CROWD_MODEL)
            return
        import torch

        blob = torch.load(config.CROWD_MODEL, map_location="cpu", weights_only=True)
        self.net = build_tcn()
        self.net.load_state_dict(blob["state"])
        self.net.eval()
        self.mean = np.array(blob["mean"], dtype=np.float32)
        self.std = np.array(blob["std"], dtype=np.float32)
        self.torch = torch
        self.available = True

    def prob(self, window: np.ndarray) -> float:
        x = (window - self.mean) / self.std
        with self.torch.no_grad():
            t = self.torch.from_numpy(x.T[None].astype(np.float32))
            return float(self.torch.sigmoid(self.net(t))[0, 0])


_model: CrowdModel | None = None


def get_crowd_model() -> CrowdModel:
    global _model
    if _model is None:
        _model = CrowdModel()
    return _model


class CrowdEngine:
    type = "crowd"

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.feat = CrowdFeatures()
        self.window: deque = deque(maxlen=WINDOW)
        self.baseline: deque = deque(maxlen=300)  # ~30 s of calm-state flow
        self.p_smooth = 0.0
        self.last_prob = 0.0
        self.persons: list = []
        self.recent_n: deque = deque(maxlen=50)  # people counts over the last ~5 s

    def reset(self) -> None:
        self.__init__(self.camera_id)

    def process(self, f: Frame) -> list[Candidate]:
        if f.fresh:
            self.persons = [t for t in f.tracks if t.cls == "person"]
        persons = self.persons
        x = self.feat.step(f.image, f.ts, persons)
        out: list[Candidate] = []
        n = len(persons)
        self.recent_n.append(n)
        crowd_size = max(self.recent_n)  # people run out of frame, so use the recent peak
        if x is not None:
            self.window.append(x)
            model = get_crowd_model()
            if model.available and len(self.window) == WINDOW:
                p = model.prob(np.stack(self.window))
                source = "temporal CNN"
            elif not model.available and len(self.baseline) > 50:
                base = np.array(self.baseline)
                z = (x[2] - base.mean()) / (base.std() + 1e-6)
                p = float(min(0.9, max(0.0, 0.5 + 0.1 * (z - 3))))
                source = "motion z-score fallback"
            else:
                p, source = 0.0, ""
            self.p_smooth = 0.6 * self.p_smooth + 0.4 * p
            self.last_prob = self.p_smooth
            if self.p_smooth < 0.5:
                self.baseline.append(float(x[2]))
            if self.p_smooth >= 0.5 and crowd_size >= MIN_CROWD:
                base = float(np.mean(self.baseline)) if self.baseline else 0.0
                ratio = float(x[2]) / base if base > 1e-6 else None
                out.append(Candidate(
                    type="crowd", camera_id=self.camera_id, key="panic", conf=self.p_smooth,
                    ts=f.ts, box=_union(persons), subtype="sudden dispersal",
                    details={"people": crowd_size, "source": source,
                             "motion_ratio": round(ratio, 1) if ratio else None,
                             "speed_max": round(float(x[6]), 2)}))
        limit = config.CROWD_LIMIT
        if f.fresh and n >= limit:
            out.append(Candidate(
                type="crowd", camera_id=self.camera_id, key="overcrowding",
                conf=min(0.95, 0.65 + 0.02 * (n - limit)), ts=f.ts, box=_union(persons),
                subtype="overcrowding", details={"people": n, "limit": limit, "source": "count rule"}))
        return out


def _union(tracks: list):
    if not tracks:
        return None
    return (min(t.box[0] for t in tracks), min(t.box[1] for t in tracks),
            max(t.box[2] for t in tracks), max(t.box[3] for t in tracks))
