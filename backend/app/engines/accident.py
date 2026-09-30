"""Traffic-accident engine.

Learned part: a YOLO accident detector (see BENCH.md for which weights and why), run about
once a second per traffic camera. Rule part: a trajectory check on tracked vehicles (two
overlapping vehicles where a moving one stops abruptly). The rule alone scores below the
confidence gate when the model is loaded, so it supports the model rather than replacing
it; with no model weights it becomes the fallback detector.

The trajectory idea follows the tracking-based approaches listed in DISCOVERY.md
(neyvur/traffic-video-analysis, kircova/Car-Crash-Detection); the code is our own.
"""
from __future__ import annotations

import math
from collections import deque

from .. import config
from ..schema import Candidate, Frame, Track, iou

NEGATIVE_WORDS = ("non", "no_", "no-", "no ", "vehicle", "car", "normal")
POSITIVE_WORDS = ("accident", "crash", "collision", "severe", "moderate")
MODEL_HOLD_S = 2.5


def is_accident_class(name: str) -> bool:
    n = name.lower()
    if any(n.startswith(w) or n == w.strip() for w in NEGATIVE_WORDS):
        return False
    return any(w in n for w in POSITIVE_WORDS)


class AccidentEngine:
    type = "accident"

    def __init__(self, camera_id: str, model_available: bool = True):
        self.camera_id = camera_id
        self.model_available = model_available
        self.hist: dict[int, deque] = {}
        self.pair_since: dict[tuple[int, int], float] = {}
        self.model_hit: dict | None = None
        self.model_ts = -1e9

    def reset(self) -> None:
        self.__init__(self.camera_id, self.model_available)

    # -- trajectory rule
    def _speed(self, tid: int, t0: float, t1: float) -> float | None:
        pts = [p for p in self.hist.get(tid, ()) if t0 <= p[0] <= t1]
        if len(pts) < 2 or pts[-1][0] - pts[0][0] < 0.25:
            return None
        d = math.hypot(pts[-1][1] - pts[0][1], pts[-1][2] - pts[0][2])
        return d / pts[-1][3] / (pts[-1][0] - pts[0][0])  # own box-sizes per second

    def _rule(self, f: Frame, vehicles: list[Track], persons: list[Track]) -> tuple[float, dict] | None:
        live_pairs = set()
        best: tuple[float, dict] | None = None
        for i, a in enumerate(vehicles):
            for b in vehicles[i + 1:]:
                if iou(a.box, b.box) < 0.08:
                    continue
                key = (min(a.id, b.id), max(a.id, b.id))
                live_pairs.add(key)
                since = self.pair_since.setdefault(key, f.ts)
                before = [self._speed(t.id, f.ts - 3.0, f.ts - 0.8) for t in (a, b)]
                now = [self._speed(t.id, f.ts - 0.8, f.ts) for t in (a, b)]
                if None in now or all(s is None for s in before):
                    continue
                peak = max(s for s in before if s is not None)
                if peak < 0.6 or max(now) > 0.3 * peak or f.ts - since < 0.4:
                    continue
                ux1, uy1 = min(a.box[0], b.box[0]), min(a.box[1], b.box[1])
                ux2, uy2 = max(a.box[2], b.box[2]), max(a.box[3], b.box[3])
                near = sum(1 for p in persons
                           if ux1 - p.width <= p.center[0] <= ux2 + p.width and uy1 <= p.foot[1] <= uy2 + p.height)
                conf = (0.4 if self.model_available else 0.5) + (0.1 if near else 0.0) \
                    + (0.1 if peak > 1.5 else 0.0)
                d = {"rule": f"vehicles {a.id} and {b.id} overlap after an abrupt stop "
                             f"(speed fell from {peak:.1f} to {max(now):.1f} box-lengths/s)",
                     "rule_box": (ux1, uy1, ux2, uy2), "rule_people": near}
                if best is None or conf > best[0]:
                    best = (conf, d)
        for k in [k for k in self.pair_since if k not in live_pairs]:
            del self.pair_since[k]
        return best

    def process(self, f: Frame) -> list[Candidate]:
        vehicles = [t for t in f.tracks if t.cls in config.VEHICLES]
        persons = [t for t in f.tracks if t.cls == "person"]
        if f.fresh:
            live = set()
            for t in vehicles:
                live.add(t.id)
                self.hist.setdefault(t.id, deque(maxlen=60)).append(
                    (f.ts, t.center[0], t.center[1], max(math.hypot(t.width, t.height), 1.0)))
            for tid in [k for k in self.hist if k not in live and f.ts - self.hist[k][-1][0] > 3]:
                del self.hist[tid]

        model_ran = f.accident_dets is not None
        if model_ran:
            hits = [d for d in f.accident_dets if is_accident_class(d["cls"])]
            if hits:
                self.model_hit = max(hits, key=lambda d: d["conf"])
                self.model_ts = f.ts
            else:
                self.model_hit = None
        if not (f.fresh or model_ran):
            return []

        rule = self._rule(f, vehicles, persons) if f.fresh else None
        m = self.model_hit if (self.model_hit and f.ts - self.model_ts <= MODEL_HOLD_S) else None
        if not m and not rule:
            return []
        if m and not model_ran and not rule:
            return []  # nothing new this frame; do not count the same model hit twice

        m_conf = m["conf"] if m else 0.0
        r_conf = rule[0] if rule else 0.0
        conf = 1 - (1 - m_conf) * (1 - r_conf) if (m and rule) else max(m_conf, r_conf)
        box = m["box"] if m else rule[1]["rule_box"]
        inside = [v for v in vehicles if iou(v.box, box) > 0.02]
        if m and not inside and not rule:
            # our check on the learned model: an "accident" box with no tracked vehicle in it
            conf *= 0.5
        people = sum(1 for p in persons
                     if box[0] - p.width <= p.center[0] <= box[2] + p.width and box[1] <= p.foot[1] <= box[3] + p.height)
        details = {"vehicles": len(inside), "people": people,
                   "sources": [s for s, on in (("accident model", bool(m)), ("trajectory rule", bool(rule))) if on]}
        if m:
            details.update(model_class=m["cls"], model_conf=round(m_conf, 2),
                           vehicle_check="passed" if inside else "no tracked vehicle in the box")
        if rule:
            details.update(rule=rule[1]["rule"])
        return [Candidate(type="accident", camera_id=self.camera_id, key="accident", conf=conf,
                          ts=f.ts, box=box, subtype=(m["cls"] if m else "collision"), details=details)]
