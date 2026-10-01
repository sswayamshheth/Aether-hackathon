"""Trajectory-level scenario simulator (method A of the synthetic suite).

A scenario spec (tests/scenarios/<category>/<id>.yaml) names a generator and a set of
conditions. The generator scripts objects (people, vehicles, bags) as keyframed boxes over
time; the conditions turn those exact boxes into what a real detector + tracker would hand
the engines: missed detections, box jitter, ID switches, lower detection rate, occlusion
gaps, camera shake, lower confidence at night / in rain or fog, and small or large objects
depending on distance. The result replays through the real app (Pipeline in cache mode:
same engines, same false-alarm filter, same incident manager) without any video or YOLO.

The images handed to the pipeline are rendered from the same boxes (textured rectangles on
a noisy background) so the crowd engine's optical-flow features see the motion. They are
not photo-realistic: crowd results on method A test the logic, not the vision.

The auxiliary models are "silent" by default: they answer on their live cadence with no
detections and a neutral scene score, so method A measures the rules and the filter alone.
A scenario may script model output explicitly (conditions.models), which is recorded in the
spec so the report can separate "logic only" from "logic + scripted model" results.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import cv2
import numpy as np

W, H = 640, 360
SIZES = {"car": (70, 40), "bus": (150, 60), "truck": (120, 55), "motorcycle": (30, 30), "bicycle": (28, 30),
         "person": (18, 46), "suitcase": (18, 22), "backpack": (14, 18), "handbag": (14, 14)}
DIST_SCALE = {"near": 1.25, "mid": 0.85, "far": 0.5}
NEUTRAL_SCENE_GROUPS = ["fire", "smoke", "explosion", "flood", "fight", "robbery", "vandalism", "crash",
                        "collapse", "animal", "weapon"]


@dataclass
class Obj:
    id: int
    cls: str
    keys: list[tuple[float, float, float, float, float]]  # (t, cx, cy, w, h), linear between keys
    t_on: float = 0.0
    t_off: float = 1e9
    det_rate: float = 1.0  # per-detection probability of being seen (bags are often missed)
    conf: float = 0.8
    gaps: list[tuple[float, float]] = field(default_factory=list)  # occluded intervals

    def at(self, t: float):
        if t < self.t_on or t > self.t_off:
            return None
        k = self.keys
        if t <= k[0][0]:
            return k[0][1:]
        for a, b in zip(k, k[1:]):
            if a[0] <= t <= b[0]:
                u = (t - a[0]) / max(b[0] - a[0], 1e-9)
                return tuple(a[i] + u * (b[i] - a[i]) for i in range(1, 5))
        return k[-1][1:]


class World:
    """Holds scripted objects in one camera view, with the view's scale and heading."""

    def __init__(self, rng: random.Random, dist: str = "mid", angle: float = 0.0):
        self.rng = rng
        self.s = DIST_SCALE.get(dist, 0.85)
        self.angle = math.radians(angle)
        self.objs: list[Obj] = []
        self._id = 1
        self.zones: list[dict] = []

    def size(self, cls: str) -> tuple[float, float]:
        w, h = SIZES[cls]
        return w * self.s, h * self.s

    def rot(self, x: float, y: float) -> tuple[float, float]:
        """Rotate a point about the frame centre by the view heading (keeps it in frame)."""
        cx, cy = W / 2, H / 2
        dx, dy = x - cx, y - cy
        c, s = math.cos(self.angle), math.sin(self.angle)
        rx, ry = cx + c * dx - s * dy, cy + (s * dx + c * dy) * 0.6
        return min(max(rx, 5), W - 5), min(max(ry, 5), H - 5)

    def add(self, cls: str, path: list[tuple[float, float, float]], t_on: float = 0.0, t_off: float = 1e9,
            size: tuple[float, float] | None = None, sizes: list[tuple[float, float]] | None = None,
            **kw) -> Obj:
        """path: (t, x, y) in an unrotated 640x360 layout, travel along +x by default."""
        w, h = size or self.size(cls)
        keys = []
        for i, (t, x, y) in enumerate(path):
            ww, hh = sizes[i] if sizes else (w, h)
            rx, ry = self.rot(x, y)
            keys.append((t, rx, ry, ww, hh))
        o = Obj(self._id, cls, keys, t_on, t_off, **kw)
        self._id += 1
        self.objs.append(o)
        return o

    def lane(self, name: str, y: float, kind: str = "lane", half: float = 30.0) -> None:
        pts = [self.rot(0, y - half), self.rot(W, y - half), self.rot(W, y + half), self.rot(0, y + half)]
        self.zones.append({"name": name, "kind": kind, "points": [[x / W, yy / H] for x, yy in pts]})

    def rect_zone(self, name: str, kind: str, x1: float, y1: float, x2: float, y2: float) -> None:
        pts = [self.rot(x1, y1), self.rot(x2, y1), self.rot(x2, y2), self.rot(x1, y2)]
        self.zones.append({"name": name, "kind": kind, "points": [[x / W, yy / H] for x, yy in pts]})


# ------------------------------------------------------------------ conditions -> detector noise
def noise_model(cond: dict) -> dict:
    light, weather = cond.get("light", "day"), cond.get("weather", "clear")
    m = {"miss": float(cond.get("miss", 0.03)), "jitter": float(cond.get("jitter", 0.02)),
         "conf_drop": 0.0, "shake": float(cond.get("shake", 0.0)),
         "id_switch": bool(cond.get("id_switch", False)), "detect_fps": float(cond.get("fps", 5.0))}
    if light == "night":
        m["miss"] += 0.12
        m["jitter"] *= 1.5
        m["conf_drop"] += 0.15
    if weather == "rain":
        m["miss"] += 0.08
        m["conf_drop"] += 0.05
    elif weather == "fog":
        m["miss"] += 0.1
        m["conf_drop"] += 0.1
    if cond.get("distance") == "far":
        m["miss"] += 0.05
    return m


def neutral_aux(ts: float, last: dict, scene_override: dict | None = None) -> dict:
    """What the auxiliary models answer on their live cadence when they see nothing."""
    aux = {}
    for name, every in (("accident", 1.0), ("fire", 1.0), ("weapon", 0.5), ("fall", 1.0), ("violence", 1.0),
                        ("scene", 2.0)):
        if ts - last.get(name, -1e9) >= every - 1e-6:
            last[name] = ts
            if name == "violence":
                aux[name] = {"p": 0.05}
            elif name == "scene":
                groups = {g: 0.05 for g in NEUTRAL_SCENE_GROUPS}
                if scene_override:
                    groups.update(scene_override)
                aux[name] = {"groups": groups, "normal": 0.12}
            else:
                aux[name] = {"dets": []}
    return aux


def render_tracks(world: World, cond: dict, duration: float, seed: int, model_script=None) -> dict:
    """Turn a world into a cache {frame_idx: record} at the camera's frame rate plus images."""
    rng = random.Random(seed)
    nm = noise_model(cond)
    cam_fps = float(cond.get("cam_fps", 10.0))
    detect_every = max(1, round(cam_fps / nm["detect_fps"]))
    frames: dict[str, dict] = {}
    timeline: list[tuple[int, float]] = []
    last_aux: dict = {}
    id_map: dict[int, int] = {}
    switch_at = {o.id: rng.uniform(0.3, 0.7) * duration for o in world.objs} if nm["id_switch"] else {}
    next_alias = 1000
    gap = cond.get("stream_gap")  # (start, end): no frames at all (RTSP disconnect)
    n = int(duration * cam_fps)
    for i in range(n):
        ts = i / cam_fps
        if gap and gap[0] <= ts < gap[1]:
            continue
        fresh = i % detect_every == 0
        rec: dict = {"fresh": fresh, "tracks": []}
        if fresh:
            sx = sy = 0.0
            if nm["shake"]:
                sx, sy = rng.gauss(0, nm["shake"]), rng.gauss(0, nm["shake"] * 0.6)
            for o in world.objs:
                p = o.at(ts)
                if p is None or any(a <= ts < b for a, b in o.gaps):
                    continue
                if rng.random() > o.det_rate or rng.random() < nm["miss"]:
                    continue
                cx, cy, w, h = p
                j = nm["jitter"] * max(w, h)
                cx, cy = cx + rng.gauss(0, j) + sx, cy + rng.gauss(0, j) + sy
                w, h = w * (1 + rng.gauss(0, nm["jitter"])), h * (1 + rng.gauss(0, nm["jitter"]))
                if cx < 0 or cx > W or cy < 0 or cy > H:
                    continue
                tid = o.id
                if o.id in switch_at and ts >= switch_at[o.id]:
                    if o.id not in id_map:
                        id_map[o.id] = next_alias
                        next_alias += 1
                    tid = id_map[o.id]
                if o.cls in ("suitcase", "backpack", "handbag"):
                    tid = 0  # bags bypass the tracker in the app
                conf = max(0.05, min(0.99, o.conf - nm["conf_drop"] + rng.gauss(0, 0.04)))
                rec["tracks"].append([tid, o.cls, round(cx - w / 2, 1), round(cy - h / 2, 1),
                                      round(cx + w / 2, 1), round(cy + h / 2, 1), round(conf, 3)])
        aux = neutral_aux(ts, last_aux)
        if model_script:
            model_script(ts, aux, rng)
        rec["aux"] = aux or None
        frames[str(i)] = rec
        timeline.append((i, ts))
    return {"frames": frames, "timeline": timeline, "fps": cam_fps / detect_every * detect_every,
            "zones": world.zones, "cond": cond}


def render_image(world: World, ts: float, cond: dict, rng: np.random.Generator, bg: np.ndarray) -> np.ndarray:
    """Draw at quarter resolution and upscale: the crowd engine computes optical flow on a
    160x120 copy anyway, and the frame keeps the full 640x360 size the zones are defined on."""
    img = bg.copy()
    q = 4
    for o in world.objs:
        p = o.at(ts)
        if p is None:
            continue
        cx, cy, w, h = p
        x1, y1, x2, y2 = int((cx - w / 2) / q), int((cy - h / 2) / q), int((cx + w / 2) / q), int((cy + h / 2) / q)
        shade = {"person": 200, "car": 150, "bus": 120, "truck": 110, "motorcycle": 170}.get(o.cls, 90)
        cv2.rectangle(img, (x1, y1), (x2, y2), (shade, shade - 20, shade - 40), -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (30, 30, 30), 1)
    if cond.get("light") == "night":
        img = (img * 0.35).astype(np.uint8)
    noise = rng.integers(-8 if cond.get("weather") == "clear" else -16, 9 if cond.get("weather") == "clear" else 17,
                         img.shape[:2], dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise[..., None], 0, 255).astype(np.uint8)
    return cv2.resize(img, (W, H), interpolation=cv2.INTER_NEAREST)


def background(seed: int) -> np.ndarray:
    r = np.random.default_rng(seed)
    base = r.integers(70, 110, (H // 32, W // 32, 1)).astype(np.uint8)
    base = cv2.resize(np.repeat(base, 3, axis=2), (W // 4, H // 4), interpolation=cv2.INTER_LINEAR)
    return base
