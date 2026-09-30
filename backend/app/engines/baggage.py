"""Unattended-baggage engine.

The bag itself comes from the detector (COCO backpack / handbag / suitcase). Everything
after that is explicit spatio-temporal logic, on purpose: "who owns this bag and how long
have they been away" has to be explainable to an operator.

  1. Bags are remembered by position, not tracker ID, so a flickering detection or an ID
     switch does not reset the clock.
  2. Owner = the person who was closest to the bag while it was first seen.
  3. A bag is attended only while its owner is near. Other people walking past do not
     make it attended (owner-away verification).
  4. Stationary + owner away for BAG_UNATTENDED_S -> "unattended"; BAG_ABANDONED_S -> "abandoned".

Logic is our own; the owner-proximity idea is common to the baggage repos in DISCOVERY.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import config
from ..schema import Candidate, Frame, Track

NEAR_K = 0.9  # a person is "near" within this many of their own box heights
MISSING_GRACE_S = 8.0  # keep a bag through short occlusions
MIN_SIGHTINGS = 6  # a bag must be detected this many times before it can raise anything
HANDOVER_S = 6.0  # owner track lost, new track appears at the same spot: same person


@dataclass
class Bag:
    id: int
    cls: str
    box: tuple[float, float, float, float]
    first_ts: float
    last_ts: float
    anchor: tuple[float, float]  # where it was last judged stationary
    stationary_since: float
    owner: int | None = None
    owner_votes: dict[int, float] = field(default_factory=dict)
    owner_last_near: float | None = None
    owner_last_pos: tuple[float, float] | None = None
    away_since: float | None = None
    confs: list[float] = field(default_factory=list)
    others_near: int = 0

    @property
    def center(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2

    @property
    def diag(self) -> float:
        return math.hypot(self.box[2] - self.box[0], self.box[3] - self.box[1])


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _near(bag: Bag, p: Track) -> bool:
    d = min(_dist(bag.center, p.foot), _dist(bag.center, p.center))
    return d < NEAR_K * max(p.height, 1.5 * bag.diag)


class BaggageEngine:
    type = "baggage"

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.bags: dict[int, Bag] = {}
        self._next = 1

    def reset(self) -> None:
        self.bags.clear()

    def _match(self, det: Track) -> Bag | None:
        best, best_d = None, 1e9
        for b in self.bags.values():
            d = _dist(b.center, det.center)
            if d < max(b.diag, 20) and d < best_d:
                best, best_d = b, d
        return best

    def process(self, f: Frame) -> list[Candidate]:
        if not f.fresh:
            return []
        persons = [t for t in f.tracks if t.cls == "person"]
        seen: set[int] = set()
        for det in (t for t in f.tracks if t.cls in config.BAGS):
            bag = self._match(det)
            if bag is None:
                bag = Bag(self._next, det.cls, det.box, f.ts, f.ts, det.center, f.ts)
                self.bags[bag.id] = bag
                self._next += 1
            else:
                a = 0.4  # smooth the box so jitter is not read as movement
                bag.box = tuple(a * n + (1 - a) * o for n, o in zip(det.box, bag.box))
                bag.last_ts = f.ts
            bag.confs = (bag.confs + [det.conf])[-30:]
            seen.add(bag.id)

        out: list[Candidate] = []
        for bag in list(self.bags.values()):
            if f.ts - bag.last_ts > MISSING_GRACE_S:
                del self.bags[bag.id]
                continue
            if bag.id in seen and _dist(bag.center, bag.anchor) > 0.6 * bag.diag:
                # it moved: someone is carrying it, restart everything
                bag.anchor, bag.stationary_since, bag.away_since = bag.center, f.ts, None
            near = [p for p in persons if _near(bag, p)]
            self._update_owner(bag, near, persons, f.ts)
            owner_near = any(p.id == bag.owner for p in near)
            bag.others_near = sum(1 for p in near if p.id != bag.owner)
            if owner_near:
                bag.away_since = None
            elif bag.away_since is None:
                bag.away_since = f.ts

            if bag.away_since is None:
                continue
            away = f.ts - bag.away_since
            still = f.ts - bag.stationary_since
            if away < config.BAG_UNATTENDED_S or still < config.BAG_UNATTENDED_S or len(bag.confs) < MIN_SIGHTINGS:
                continue
            abandoned = away >= config.BAG_ABANDONED_S
            conf = sum(bag.confs) / len(bag.confs)
            owner_txt = (f"owner (track {bag.owner}) away {away:.0f}s" if bag.owner is not None
                         else f"no owner seen near it for {away:.0f}s")
            out.append(Candidate(
                type="baggage", camera_id=self.camera_id, key=f"bag{bag.id}", conf=conf, ts=f.ts,
                box=bag.box, subtype="abandoned" if abandoned else "unattended",
                details={"object": bag.cls, "owner_track": bag.owner, "owner_away_s": round(away, 1),
                         "stationary_s": round(still, 1), "people_nearby": bag.others_near,
                         "owner_text": owner_txt, "people": len(persons)}))
        return out

    def _update_owner(self, bag: Bag, near: list[Track], persons: list[Track], ts: float) -> None:
        age = ts - bag.first_ts
        if age <= 3.0 or bag.owner is None:
            # ownership window: whoever is closest while the bag first appears
            for p in near:
                d = _dist(bag.center, p.foot) + 1.0
                bag.owner_votes[p.id] = bag.owner_votes.get(p.id, 0.0) + 1.0 / d
            if bag.owner_votes and age <= 3.0 or (bag.owner is None and bag.owner_votes):
                bag.owner = max(bag.owner_votes, key=bag.owner_votes.get)
        owner = next((p for p in persons if p.id == bag.owner), None)
        if owner is not None:
            if _near(bag, owner):
                bag.owner_last_near, bag.owner_last_pos = ts, owner.foot
            return
        # owner track is gone. If a new track stands where the owner just was, it is the
        # same person with a new tracker ID.
        if bag.owner is not None and bag.owner_last_near and ts - bag.owner_last_near < HANDOVER_S:
            for p in near:
                if bag.owner_last_pos and _dist(p.foot, bag.owner_last_pos) < 0.5 * p.height:
                    bag.owner, bag.owner_last_near, bag.owner_last_pos = p.id, ts, p.foot
                    return
