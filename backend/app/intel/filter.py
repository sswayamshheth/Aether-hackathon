"""False-alarm filter. Engines emit per-frame candidates; this decides which become events.

Four checks, each of which can suppress a candidate and each of which is logged:
  zone mask        candidate sits inside an operator-drawn "ignore" zone
  confidence gate  mean confidence below the gate for that camera (gate moves with
                   operator Confirm / Dismiss feedback)
  persistence      not enough hits over enough time
  camera agreement another camera in the same area already sees the same type, which
                   relaxes the gate and halves the persistence needed
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .. import config
from ..schema import Candidate, Frame, zone_at


@dataclass
class Group:
    first_ts: float
    last_ts: float
    hits: int = 0
    conf_sum: float = 0.0
    max_conf: float = 0.0
    confirmed: bool = False
    masked: bool = False
    last: Candidate | None = None
    raw_counted: bool = False
    confs: list[float] = field(default_factory=list)

    @property
    def mean_conf(self) -> float:
        recent = self.confs[-8:]
        return sum(recent) / len(recent) if recent else 0.0


class FalseAlarmFilter:
    def __init__(self, threshold_adj: Callable[[str, str], float],
                 on_suppressed: Callable[[dict], None],
                 area_active: Callable[[str, str, float], bool] | None = None):
        self.groups: dict[tuple[str, str, str], Group] = {}
        self.threshold_adj = threshold_adj
        self.on_suppressed = on_suppressed
        self.area_active = area_active or (lambda cam, typ, ts: False)
        self.raw_alarms = 0  # what an unfiltered system would have raised

    def gate(self, camera_id: str, typ: str) -> float:
        return config.GATE[typ] + self.threshold_adj(camera_id, typ)

    def process(self, f: Frame, cands: list[Candidate]) -> list[Candidate]:
        """Returns the candidates that are part of a confirmed event on this frame."""
        out = []
        for c in cands:
            k = (c.camera_id, c.type, c.key)
            g = self.groups.get(k)
            if g is None:
                g = self.groups[k] = Group(c.ts, c.ts)
            g.last_ts, g.last = c.ts, c
            g.hits += 1
            g.confs.append(c.conf)
            g.max_conf = max(g.max_conf, c.conf)
            if not g.raw_counted:
                g.raw_counted = True
                self.raw_alarms += 1

            z = zone_at(f, c.box, {"ignore"})
            if z is not None:
                g.masked = True
                continue
            zr = zone_at(f, c.box, {"restricted", "lane", "crowd"})
            if zr is not None:
                c.details.update(zone=zr["name"], zone_kind=zr["kind"])

            agree = self.area_active(c.camera_id, c.type, c.ts)
            gate = self.gate(c.camera_id, c.type) - (0.10 if agree else 0.0)
            persist = config.PERSIST_S[c.type] * (0.5 if agree else 1.0)
            hits = max(1, config.MIN_HITS[c.type] - (1 if agree else 0))
            if g.confirmed or (g.mean_conf >= gate and g.hits >= hits
                               and c.ts - g.first_ts >= persist):
                g.confirmed = True
                c.details["gate"] = round(gate, 2)
                out.append(c)
        self._expire(f.camera_id, f.ts)
        return out

    def _expire(self, camera_id: str, ts: float) -> None:
        for k in [k for k, g in self.groups.items()
                  if k[0] == camera_id and ts - g.last_ts > config.GROUP_GAP_S]:
            g = self.groups.pop(k)
            if g.confirmed:
                continue
            dur = g.last_ts - g.first_ts
            typ = k[1]
            if g.masked:
                reason = "inside an ignore zone"
            elif g.mean_conf < self.gate(camera_id, typ):
                reason = f"confidence {g.mean_conf:.2f} below gate {self.gate(camera_id, typ):.2f}"
            else:
                reason = (f"not persistent ({g.hits} hit{'s' if g.hits != 1 else ''} over {dur:.1f}s, "
                          f"needs {config.MIN_HITS[typ]} over {config.PERSIST_S[typ]:.1f}s)")
            self.on_suppressed({"ts": g.last_ts, "camera_id": camera_id, "type": typ,
                                "reason": reason, "conf": round(g.max_conf, 3),
                                "duration": round(dur, 2)})

    def flush(self, camera_id: str, ts: float) -> None:
        """End of a clip or stream: close every open group for this camera."""
        self._expire(camera_id, ts + config.GROUP_GAP_S + 1)

    def active(self, camera_id: str, typ: str, ts: float) -> bool:
        return any(k[0] == camera_id and k[1] == typ and ts - g.last_ts < config.GROUP_GAP_S
                   for k, g in self.groups.items())
