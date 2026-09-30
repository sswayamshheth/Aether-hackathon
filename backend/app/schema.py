from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

Box = tuple[float, float, float, float]


@dataclass
class Track:
    id: int
    cls: str
    box: Box
    conf: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2

    @property
    def foot(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, self.box[3]

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def width(self) -> float:
        return self.box[2] - self.box[0]


@dataclass
class Frame:
    camera_id: str
    ts: float  # seconds; wall clock live, video time offline
    image: np.ndarray
    tracks: list[Track]
    fresh: bool  # detector ran on this frame (tracks are not carried over)
    aux: dict[str, dict] | None = None  # outputs of the auxiliary models that ran on this frame
    zones: list[dict] = field(default_factory=list)

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.image.shape[:2]
        return w, h


@dataclass
class Candidate:
    """One engine's claim, on one frame, that something is happening."""
    type: str  # accident | crowd | baggage
    camera_id: str
    key: str  # stable within a camera for the same ongoing event
    conf: float
    ts: float
    box: Box | None
    subtype: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def iou(a: Box, b: Box) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def point_in_poly(x: float, y: float, poly: list[list[float]]) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            inside = not inside
    return inside


def zone_at(frame: Frame, box: Box | None, kinds: set[str]) -> dict | None:
    """First zone of the given kinds containing the box's ground point (normalised coords)."""
    if box is None:
        return None
    w, h = frame.size
    x, y = (box[0] + box[2]) / 2 / w, box[3] / h
    for z in frame.zones:
        if z["kind"] in kinds and point_in_poly(x, y, z["points"]):
            return z
    return None
