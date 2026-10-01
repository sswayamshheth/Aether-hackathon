"""Overnight 2026-10-01: the config-switched rules (stable defaults unchanged)."""
from __future__ import annotations

import numpy as np

from app import config
from app.engines.accident import AccidentEngine
from app.engines.extra import SecurityEngine
from app.schema import Frame, Track

IMG = np.zeros((360, 640, 3), np.uint8)


def _car(tid, x, y=190.0):
    return Track(tid, "car", (x - 30, y - 17, x + 30, y + 17), 0.8)


def _run(engine, positions, fps=5.0):
    """positions: list over time of [(id, x)]; returns every candidate."""
    out = []
    for i, cars in enumerate(positions):
        f = Frame("c", i / fps, IMG, [_car(t, x) for t, x in cars], True, {"accident": {"dets": []}})
        out += engine.process(f)
    return out


def _brake_path(x0, v, t_brake, dur, total, fps=5.0):
    xs = []
    for i in range(int(total * fps)):
        t = i / fps
        if t < t_brake:
            xs.append(x0 + v * t)
        else:
            tau = min(t - t_brake, dur)
            xs.append(x0 + v * t_brake + v * tau - v * tau * tau / (2 * dur))
    return xs


def test_abrupt_rule_ignores_gradual_braking_in_a_queue(monkeypatch):
    monkeypatch.setattr(config, "ACCIDENT_RULE", "abrupt")
    lead = _brake_path(300, 120, 4.0, 2.0, 12)
    follow = _brake_path(245, 120, 4.0, 2.0, 12)  # 55 px behind: the boxes overlap in the image
    cands = _run(AccidentEngine("c", model_available=False), [[(1, a), (2, b)] for a, b in zip(lead, follow)])
    assert not cands


def test_abrupt_rule_fires_on_an_impact_stop(monkeypatch):
    monkeypatch.setattr(config, "ACCIDENT_RULE", "abrupt")
    fps, tc = 5.0, 5.0
    pos = []
    for i in range(int(12 * fps)):
        t = i / fps
        a = 40 + 180 * min(t, tc)  # hits the slow car at tc and stops dead
        b = 40 + 180 * tc + 50 + 30 * min(t, tc) - 30 * tc
        pos.append([(1, a), (2, b)])
    cands = _run(AccidentEngine("c", model_available=False), pos)
    assert any(c.type == "accident" for c in cands)


def test_loitering_counts_from_the_recent_window(monkeypatch):
    monkeypatch.setattr(config, "LOITER_WINDOW_S", 30.0)
    monkeypatch.setattr(config, "LOITER_CONF", 0.65)
    eng = SecurityEngine("c")
    out = []
    for i in range(0, 70 * 2):
        t = i / 2
        x = 20 + 100 * t if t < 3 else 320 + 5 * np.sin(t)  # walks in, then stays
        p = Track(7, "person", (x - 9, 160, x + 9, 206), 0.8)
        out += eng.process(Frame("c", t, IMG, [p], True))
    lo = [c for c in out if c.subtype == "loitering"]
    assert lo and lo[0].conf >= config.GATE["security"]


def test_stable_defaults_unchanged():
    assert config.ACCIDENT_RULE == "v1"
    assert config.LOITER_WINDOW_S == 0 and config.LOITER_CONF == 0.55
    assert config.CROWD_FLOW_MAX == 0
