"""Incident engines beyond accident / crowd / baggage.

Every engine follows the same pattern: detector outputs (from app.aux_models) plus rules
propose a candidate, and each candidate carries a `features` dict. The ML verifier
(app.intel.verifier) decides from those features whether the candidate is real; the rules
stay as the fallback when no trained verifier exists, and as the readable explanation.

  FireEngine      fire, smoke, explosion        fire/smoke detector + scene model
  WeaponEngine    pistol, knife                 weapon detector + "held by a person" rule
  ViolenceEngine  fight / assault, robbery      violence classifier + people rules
  MedicalEngine   fall, collapse                fall detector + lying-still rule
  HazardEngine    flood, vandalism, animal      scene model (zero-shot) only
  SecurityEngine  intrusion, loitering, wrong-way driving, stalled vehicle,
                  pedestrian on the road        tracks + operator-drawn zones (rules only)
"""
from __future__ import annotations

import math
from collections import deque

from .. import config
from ..schema import Candidate, Frame, Track, point_in_poly


def _area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _margin(scene: dict | None, group: str) -> float:
    """How much more the frame looks like `group` than like an ordinary scene."""
    if not scene:
        return 0.0
    return round(scene["groups"].get(group, 0.0) - scene["normal"], 5)


class _SceneMemory:
    """Keeps the latest scene-model result for a few seconds, for use as a feature."""

    def __init__(self) -> None:
        self.scene: dict | None = None
        self.ts = -1e9

    def update(self, f: Frame) -> dict | None:
        if f.aux and "scene" in f.aux:
            self.scene, self.ts = f.aux["scene"], f.ts
        return self.scene if f.ts - self.ts < 6.0 else None


class FireEngine:
    type = "fire"

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.mem = _SceneMemory()
        self.areas: deque = deque(maxlen=10)

    def reset(self) -> None:
        self.__init__(self.camera_id)

    def process(self, f: Frame) -> list[Candidate]:
        scene = self.mem.update(f)
        if not f.aux or "fire" not in f.aux:
            return []
        w, h = f.size
        dets = f.aux["fire"]["dets"]
        fire = [d for d in dets if d["cls"] == "fire"]
        smoke = [d for d in dets if d["cls"] == "smoke"]
        m_fire, m_smoke, m_exp = _margin(scene, "fire"), _margin(scene, "smoke"), _margin(scene, "explosion")
        if not fire and not smoke and max(m_fire, m_smoke, m_exp) <= 0:
            self.areas.clear()
            return []
        area = sum(_area(d["box"]) for d in fire + smoke) / (w * h)
        self.areas.append(area)
        growth = (self.areas[-1] - self.areas[0]) if len(self.areas) > 1 else 0.0
        conf = max([d["conf"] for d in fire + smoke] or [0.0])
        subtype = "explosion" if m_exp > max(m_fire, m_smoke, 0) else ("fire" if fire else "smoke")
        box = _union([d["box"] for d in fire + smoke])
        feats = {"fire_conf": max([d["conf"] for d in fire] or [0.0]),
                 "smoke_conf": max([d["conf"] for d in smoke] or [0.0]),
                 "area": round(area, 4), "growth": round(growth, 4), "boxes": len(fire) + len(smoke),
                 "scene_fire": m_fire, "scene_smoke": m_smoke, "scene_explosion": m_exp}
        return [Candidate("fire", self.camera_id, "fire", conf if conf else 0.3, f.ts, box, subtype,
                          {"features": feats, "area_pct": round(100 * area, 1),
                           "people": sum(1 for t in f.tracks if t.cls == "person")})]


class WeaponEngine:
    type = "weapon"

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.mem = _SceneMemory()
        self.violence_p = 0.0

    def reset(self) -> None:
        self.__init__(self.camera_id)

    def process(self, f: Frame) -> list[Candidate]:
        scene = self.mem.update(f)
        if f.aux and "violence" in f.aux:
            self.violence_p = f.aux["violence"]["p"]
        if not f.aux or "weapon" not in f.aux:
            return []
        dets = f.aux["weapon"]["dets"]
        if not dets:
            return []
        persons = [t for t in f.tracks if t.cls == "person"]
        best = max(dets, key=lambda d: d["conf"])
        held = any(_held(best["box"], p) for p in persons)
        feats = {"weapon_conf": best["conf"], "held": float(held), "people": len(persons),
                 "violence_p": self.violence_p, "scene_robbery": _margin(scene, "robbery"),
                 "scene_fight": _margin(scene, "fight"), "boxes": len(dets)}
        return [Candidate("weapon", self.camera_id, "weapon", best["conf"], f.ts, tuple(best["box"]),
                          best["cls"], {"features": feats, "held_by_person": held, "people": len(persons),
                                        "object": best["cls"]})]


class ViolenceEngine:
    type = "violence"

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.mem = _SceneMemory()
        self.pos: dict[int, deque] = {}
        self.weapon_ts = -1e9

    def reset(self) -> None:
        self.__init__(self.camera_id)

    def process(self, f: Frame) -> list[Candidate]:
        scene = self.mem.update(f)
        persons = [t for t in f.tracks if t.cls == "person"]
        if f.fresh:
            live = set()
            for p in persons:
                live.add(p.id)
                self.pos.setdefault(p.id, deque(maxlen=10)).append((f.ts, *p.center, max(p.height, 1.0)))
            for k in [k for k in self.pos if k not in live]:
                del self.pos[k]
        if f.aux and f.aux.get("weapon", {}).get("dets"):
            self.weapon_ts = f.ts
        if not f.aux or "violence" not in f.aux:
            return []
        p = f.aux["violence"]["p"]
        m_fight, m_rob = _margin(scene, "fight"), _margin(scene, "robbery")
        if p < 0.5 and max(m_fight, m_rob) <= 0:
            return []
        if len(persons) < 2 and max(m_fight, m_rob) <= 0:
            return []  # rule: a fight needs at least two people unless the scene model sees one
        close = _closest_pair(persons)
        speeds = [_speed(q) for q in self.pos.values()]
        speeds = [s for s in speeds if s is not None]
        armed = f.ts - self.weapon_ts < 5.0
        subtype = "robbery" if (armed or m_rob > m_fight) else "fight"
        feats = {"violence_p": p, "people": len(persons), "closest_pair": round(close, 3),
                 "speed_max": round(max(speeds, default=0.0), 3), "speed_mean": round(
                     sum(speeds) / len(speeds), 3) if speeds else 0.0,
                 "scene_fight": m_fight, "scene_robbery": m_rob, "weapon_seen": float(armed)}
        return [Candidate("violence", self.camera_id, "violence", p, f.ts, _union([q.box for q in persons]),
                          subtype, {"features": feats, "people": len(persons), "weapon_seen": armed})]


class MedicalEngine:
    type = "medical"

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.mem = _SceneMemory()
        self.lying: dict[int, tuple[float, tuple[float, float]]] = {}

    def reset(self) -> None:
        self.__init__(self.camera_id)

    def process(self, f: Frame) -> list[Candidate]:
        scene = self.mem.update(f)
        out: list[Candidate] = []
        if f.fresh:  # rule: a person whose box is wider than tall, and who stays put
            live = set()
            for p in (t for t in f.tracks if t.cls == "person"):
                if p.width > 1.15 * p.height:
                    live.add(p.id)
                    first = self.lying.get(p.id)
                    if first is None or math.dist(first[1], p.center) > 0.5 * p.width:
                        self.lying[p.id] = (f.ts, p.center)
            for k in [k for k in self.lying if k not in live]:
                del self.lying[k]
        fallen = []
        if f.aux and "fall" in f.aux:
            fallen = [d for d in f.aux["fall"]["dets"] if d["cls"] == "fallen"]
        still = max((f.ts - t0 for t0, _ in self.lying.values()), default=0.0)
        m_col = _margin(scene, "collapse")
        if not fallen and still < 3.0:
            return out
        if not (f.aux and ("fall" in f.aux or "scene" in f.aux)) and not fallen:
            return out  # only decide when a model has spoken this frame
        best = max(fallen, key=lambda d: d["conf"]) if fallen else None
        conf = best["conf"] if best else 0.35
        feats = {"fallen_conf": best["conf"] if best else 0.0, "fallen_boxes": len(fallen),
                 "lying_still_s": round(still, 1), "scene_collapse": m_col,
                 "people": sum(1 for t in f.tracks if t.cls == "person")}
        subtype = "collapse" if still >= config.COLLAPSE_S else "fall"
        box = tuple(best["box"]) if best else None
        out.append(Candidate("medical", self.camera_id, "medical", conf, f.ts, box, subtype,
                             {"features": feats, "lying_still_s": round(still, 1),
                              "people": feats["people"]}))
        return out


class HazardEngine:
    """Long-tail incidents with no dedicated detector: the scene model alone."""
    type = "hazard"
    GROUPS = ("flood", "vandalism", "animal")

    def __init__(self, camera_id: str):
        self.camera_id = camera_id

    def reset(self) -> None:
        pass

    def process(self, f: Frame) -> list[Candidate]:
        if not f.aux or "scene" not in f.aux:
            return []
        scene = f.aux["scene"]
        margins = {g: _margin(scene, g) for g in self.GROUPS}
        g, m = max(margins.items(), key=lambda kv: kv[1])
        if m <= config.HAZARD_MARGIN:
            return []
        feats = {f"scene_{k}": v for k, v in margins.items()} | {"scene_prob": scene["groups"][g]}
        return [Candidate("hazard", self.camera_id, f"hazard-{g}", min(0.95, 0.5 + 5 * m), f.ts, None, g,
                          {"features": feats, "scene_margin": m})]


class SecurityEngine:
    """Rules on tracks and zones. No labelled data exists for these here, so they stay
    rule-only; each needs the operator to draw the relevant zone except loitering."""
    type = "security"

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.seen: dict[int, deque] = {}
        self.lane_dirs: dict[str, deque] = {}

    def reset(self) -> None:
        self.__init__(self.camera_id)

    def process(self, f: Frame) -> list[Candidate]:
        if not f.fresh:
            return []
        w, h = f.size
        out: list[Candidate] = []
        live = set()
        for t in f.tracks:
            if t.cls in config.BAGS:
                continue
            live.add(t.id)
            self.seen.setdefault(t.id, deque(maxlen=900)).append((f.ts, *t.center, t.height))
        for k in [k for k in self.seen if k not in live and f.ts - self.seen[k][-1][0] > 10]:
            del self.seen[k]

        zones = {z["kind"]: [] for z in f.zones}
        for z in f.zones:
            zones[z["kind"]].append(z)

        def inside(t: Track, kind: str):
            x, y = t.foot[0] / w, t.foot[1] / h
            return next((z for z in zones.get(kind, []) if point_in_poly(x, y, z["points"])), None)

        for t in f.tracks:
            hist = self.seen.get(t.id)
            if not hist:
                continue
            present = f.ts - hist[0][0]
            if t.cls == "person":
                z = inside(t, "restricted")
                if z:
                    out.append(self._c(f, f"intrude{t.id}", 0.8, t, "intrusion",
                                       {"zone": z["name"], "zone_kind": "restricted", "people": 1}))
                z = inside(t, "lane")
                if z and present >= 3:
                    out.append(self._c(f, f"ped{t.id}", 0.6, t, "pedestrian on road",
                                       {"zone": z["name"], "zone_kind": "lane", "people": 1}))
                if present >= config.LOITER_S:
                    xs = [p[1] for p in hist]
                    ys = [p[2] for p in hist]
                    spread = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) / max(t.height, 1)
                    if spread < 3.0:
                        out.append(self._c(f, f"loiter{t.id}", 0.55, t, "loitering",
                                           {"present_s": round(present), "people": 1}))
            elif t.cls in config.VEHICLES:
                z = inside(t, "lane")
                recent = [p for p in hist if f.ts - p[0] <= 2.0]
                if len(recent) >= 3:
                    dx, dy = recent[-1][1] - recent[0][1], recent[-1][2] - recent[0][2]
                    moved = math.hypot(dx, dy) / max(t.height, 1)
                    if z and moved > 1.0:  # learn the lane's usual direction, flag the opposite
                        dq = self.lane_dirs.setdefault(z["name"], deque(maxlen=200))
                        n = math.hypot(dx, dy)
                        u = (dx / n, dy / n)
                        if len(dq) >= 20:
                            mx, my = sum(d[0] for d in dq) / len(dq), sum(d[1] for d in dq) / len(dq)
                            if u[0] * mx + u[1] * my < -0.5:
                                out.append(self._c(f, f"wrong{t.id}", 0.75, t, "wrong-way driving",
                                                   {"zone": z["name"], "vehicles": 1}))
                        dq.append(u)
                still = [p for p in hist if f.ts - p[0] <= config.STALLED_S]
                if z and present >= config.STALLED_S and still:
                    spread = math.hypot(max(p[1] for p in still) - min(p[1] for p in still),
                                        max(p[2] for p in still) - min(p[2] for p in still)) / max(t.height, 1)
                    if spread < 0.5:
                        out.append(self._c(f, f"stall{t.id}", 0.6, t, "stalled vehicle",
                                           {"zone": z["name"], "stopped_s": round(present), "vehicles": 1}))
        return out

    def _c(self, f: Frame, key: str, conf: float, t: Track, subtype: str, details: dict) -> Candidate:
        return Candidate("security", self.camera_id, key, conf, f.ts, t.box, subtype, details)


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _held(box, p: Track) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    m = 0.25 * p.width
    return p.box[0] - m <= cx <= p.box[2] + m and p.box[1] <= cy <= p.box[3]


def _closest_pair(persons: list[Track]) -> float:
    """Distance between the two closest people, in body heights (99 if fewer than two)."""
    best = 99.0
    for i, a in enumerate(persons):
        for b in persons[i + 1:]:
            d = math.dist(a.center, b.center) / max((a.height + b.height) / 2, 1.0)
            best = min(best, d)
    return best


def _speed(q: deque) -> float | None:
    if len(q) < 2 or q[-1][0] - q[0][0] < 0.3:
        return None
    return math.hypot(q[-1][1] - q[0][1], q[-1][2] - q[0][2]) / q[-1][3] / (q[-1][0] - q[0][0])
