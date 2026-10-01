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
LATCH_S = 8.0
IMPACT_MIN = 0.5  # box-lengths/s: slower than this is creeping, not an impact
CLOSING_MIN = 0.15  # box-diagonals the pair closed in the second before contact  # how long an impact stop keeps the rule firing while the vehicles stay stopped


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
        self.latch: dict = {}  # "abrupt" rule: impact seen at ts with this peak speed, held while the scene stays stopped
        self.model_hit: dict | None = None
        self.model_ts = -1e9
        self.scene: dict | None = None
        self.scene_ts = -1e9

    def reset(self) -> None:
        self.__init__(self.camera_id, self.model_available)

    # -- trajectory rule
    def _speed(self, tid: int, t0: float, t1: float) -> float | None:
        pts = [p for p in self.hist.get(tid, ()) if t0 <= p[0] <= t1]
        if len(pts) < 2 or pts[-1][0] - pts[0][0] < 0.25:
            return None
        d = math.hypot(pts[-1][1] - pts[0][1], pts[-1][2] - pts[0][2])
        return d / pts[-1][3] / (pts[-1][0] - pts[0][0])  # own box-sizes per second

    def _peak(self, tid: int, t0: float, t1: float, win: float = 0.6) -> float | None:
        """Fastest speed over any win-second stretch in [t0, t1] (not the average of the
        whole stretch, which a braking phase would drag down)."""
        best, t = None, t0
        while t + win <= t1 + 1e-6:
            s = self._speed(tid, t, t + win)
            if s is not None and (best is None or s > best):
                best = s
            t += 0.2
        return best

    def _rule(self, f: Frame, vehicles: list[Track], persons: list[Track]) -> tuple[float, dict] | None:
        live_pairs = set()
        best: tuple[float, dict] | None = None
        for i, a in enumerate(vehicles):
            for b in vehicles[i + 1:]:
                if iou(a.box, b.box) < 0.01:
                    continue
                key = (min(a.id, b.id), max(a.id, b.id))
                live_pairs.add(key)
                since = self.pair_since.setdefault(key, f.ts)
                if config.ACCIDENT_RULE == "abrupt":
                    hit = self._abrupt(f.ts, (a, b))
                    if hit is not None:
                        self.latch[key] = (f.ts, hit[0])
                    elif key in self.latch:
                        t_hit, pk = self.latch[key]
                        nw = [self._speed(t.id, f.ts - 0.6, f.ts) for t in (a, b)]
                        if f.ts - t_hit > LATCH_S or any(v is not None and v > 0.3 * pk for v in nw):
                            del self.latch[key]
                            continue
                        hit = (pk, [v or 0.0 for v in nw])
                    else:
                        continue
                    peak, now = hit
                else:
                    before = [self._speed(t.id, f.ts - 3.0, f.ts - 0.8) for t in (a, b)]
                    now = [self._speed(t.id, f.ts - 0.8, f.ts) for t in (a, b)]
                    if None in now or all(s is None for s in before):
                        continue
                    peak = max(s for s in before if s is not None)
                    if peak < 0.2 or max(now) > 0.8 * peak:
                        continue
                ux1, uy1 = min(a.box[0], b.box[0]), min(a.box[1], b.box[1])
                ux2, uy2 = max(a.box[2], b.box[2]), max(a.box[3], b.box[3])
                near = sum(1 for p in persons
                           if ux1 - p.width <= p.center[0] <= ux2 + p.width and uy1 <= p.foot[1] <= uy2 + p.height)
                conf = 0.7 + (0.1 if near else 0.0)
                d = {"rule": f"vehicles {a.id} and {b.id} overlap after an abrupt stop "
                             f"(speed fell from {peak:.1f} to {max(now):.1f} box-lengths/s)",
                     "rule_box": (ux1, uy1, ux2, uy2), "rule_people": near}
                if best is None or conf > best[0]:
                    best = (conf, d)
        for k in [k for k in self.pair_since if k not in live_pairs]:
            del self.pair_since[k]
        if best is None and config.ACCIDENT_RULE == "abrupt":
            best = self._solo(f, vehicles, persons)
        return best

    def _abrupt(self, ts: float, pair: tuple[Track, Track]) -> tuple[float, list[float]] | None:
        """Impact stop: some vehicle of the pair was still near its full speed 0.6-1.2 s ago
        and has (almost) stopped since, and neither is still moving fast. Braking for a light
        or in a queue sheds speed over a second or more and does not pass."""
        peak_all = [self._peak(t.id, ts - 3.0, ts - 0.6) for t in pair]
        pre = [self._speed(t.id, ts - 1.2, ts - 0.6) for t in pair]
        now = [self._speed(t.id, ts - 0.6, ts) for t in pair]
        if None in now:
            return None
        hit = False
        peak = 0.0
        for pk, pr, nw in zip(peak_all, pre, now):
            if pk is None or pr is None or pk < 0.2 or pr < IMPACT_MIN:
                continue
            peak = max(peak, pk)
            if pr >= config.ABRUPT_KEEP * pk and nw <= 0.3 * pr:
                hit = True
        if not hit or max(now) > 0.8 * peak:
            return None
        # the two must have been closing in on each other just before contact (queued cars
        # braking together keep their gap; a camera shake moves both the same way)
        gap = []
        for t0 in (ts - 1.4, ts - 0.4):
            pa = [p for p in self.hist.get(pair[0].id, ()) if abs(p[0] - t0) <= 0.35]
            pb = [p for p in self.hist.get(pair[1].id, ()) if abs(p[0] - t0) <= 0.35]
            if not pa or not pb:
                return None
            a_, b_ = pa[len(pa) // 2], pb[len(pb) // 2]
            gap.append(math.hypot(a_[1] - b_[1], a_[2] - b_[2]) / ((a_[3] + b_[3]) / 2))
        if gap[0] - gap[1] < CLOSING_MIN:
            return None
        return peak, now

    def _solo(self, f: Frame, vehicles: list[Track], persons: list[Track]) -> tuple[float, dict] | None:
        """Single vehicle (skid, pole, divider, rollover): a hard stop from real speed. On its
        own it scores just above the gate; a person lying beside it or the box changing shape
        (a fall or a roll) raises it."""
        best = None
        for v in vehicles:
            pk = self._peak(v.id, f.ts - 3.0, f.ts - 0.6)
            pr = self._speed(v.id, f.ts - 1.2, f.ts - 0.6)
            nw = self._speed(v.id, f.ts - 0.6, f.ts)
            if nw is None or ((pk is None or pr is None or pk < config.SOLO_MIN_SPEED) and ("solo", v.id) not in self.latch):
                continue
            pk, pr = pk or 0.0, pr or 0.0
            key = ("solo", v.id)
            if pr >= config.ABRUPT_KEEP * pk and nw <= 0.2 * pr:
                self.latch[key] = (f.ts, pk)
            elif key in self.latch and f.ts - self.latch[key][0] <= LATCH_S and nw <= 0.2 * self.latch[key][1]:
                pk = self.latch[key][1]
            else:
                self.latch.pop(key, None)
                continue
            h = [p for p in self.hist.get(v.id, ()) if f.ts - 3.0 <= p[0] <= f.ts - 1.2]
            shape = abs(math.hypot(v.width, v.height) - h[0][3]) / h[0][3] if h else 0.0
            lying = sum(1 for p in persons if p.width > 1.15 * p.height and
                        math.hypot(p.center[0] - v.center[0], p.center[1] - v.center[1]) < 2.5 * max(v.width, v.height))
            conf = 0.62 + (0.1 if lying else 0.0) + (0.08 if shape > 0.2 else 0.0)
            d = {"rule": f"vehicle {v.id} stopped dead from {pk:.1f} box-lengths/s"
                         + (" with a person down beside it" if lying else "")
                         + (" and its shape changed (fall or roll)" if shape > 0.2 else ""),
                 "rule_box": v.box, "rule_people": lying}
            if best is None or conf > best[0]:
                best = (conf, d)
        return best

    def process(self, f: Frame) -> list[Candidate]:
        if f.aux and "scene" in f.aux:
            self.scene = f.aux["scene"]
            self.scene_ts = f.ts
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

        model_ran = bool(f.aux) and "accident" in f.aux
        if model_ran:
            hits = [d for d in f.aux["accident"]["dets"] if is_accident_class(d["cls"])]
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
        
        # Good ML Fallback: Zero-Shot Vision-Language Model (SigLIP)
        m_crash = (self.scene["groups"].get("crash", 0.0) - self.scene["normal"]) if self.scene and (f.ts - self.scene_ts < 6.0) else 0.0
        scene_conf = min(0.95, 0.5 + 5 * m_crash) if m_crash > 0.01 else 0.0
        
        # Supervised accident classifier on the scene model's image features
        # (training/train_accident_clf.py): trained on UCF-Crime accidents and our own videos
        fresh_scene = self.scene if self.scene and (f.ts - self.scene_ts < 6.0) else None
        clf_p = fresh_scene.get("accident_p", 0.0) if fresh_scene else 0.0
        clf_hit = bool(fresh_scene) and clf_p >= fresh_scene.get("accident_thr", 1.0)

        conf = 1 - (1 - m_conf) * (1 - r_conf) if (m and rule) else max(m_conf, r_conf)
        conf = max(conf, scene_conf, clf_p if clf_hit else 0.0)

        if not m and not rule and scene_conf < 0.6 and not clf_hit:
            return []
            
        box = m["box"] if m else (rule[1]["rule_box"] if rule else (0, 0, f.size[0], f.size[1]))
        inside = [v for v in vehicles if iou(v.box, box) > 0.02]
        if m and not inside and not rule:
            # our check on the learned model: an "accident" box with no tracked vehicle in it
            conf *= 0.5
        people = sum(1 for p in persons
                     if box[0] - p.width <= p.center[0] <= box[2] + p.width and box[1] <= p.foot[1] <= box[3] + p.height)
        details = {"vehicles": len(inside), "people": people,
                   "sources": [s for s, on in (("accident model", bool(m)), ("trajectory rule", bool(rule)), ("scene model", scene_conf >= 0.6),
                                                  ("accident classifier", clf_hit)) if on]}
        details["features"] = {"model_conf": round(m_conf, 3), "rule": float(bool(rule)),
                               "vehicles": len(inside), "people": people,
                               "vehicle_check": float(bool(inside)), "rule_conf": round(r_conf, 3),
                               "scene_crash_margin": round(m_crash, 3), "accident_clf_p": round(clf_p, 3)}
        if clf_hit:
            details.update(accident_clf_p=round(clf_p, 2))
        if m:
            details.update(model_class=m["cls"], model_conf=round(m_conf, 2),
                           vehicle_check="passed" if inside else "no tracked vehicle in the box")
        if rule:
            details.update(rule=rule[1]["rule"])
        if scene_conf >= 0.6:
            details.update(scene="The scene model (SigLIP) strongly identified a car crash in the image.")
            
        return [Candidate(type="accident", camera_id=self.camera_id, key="accident", conf=conf,
                          ts=f.ts, box=box, subtype=(m["cls"] if m else "collision"), details=details)]
