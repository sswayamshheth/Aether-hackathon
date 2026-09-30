"""Incident manager: turns confirmed events into stored incidents, merges cameras that
see the same thing, keeps severity and reasons current, and records operator feedback."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from .. import config
from ..db import Store
from ..schema import Candidate
from .severity import level, score_incident

log = logging.getLogger("drishti.incidents")

TITLES = {"accident": "Traffic accident", "crowd": "Crowd anomaly", "baggage": "Unattended baggage"}


class IncidentManager:
    def __init__(self, store: Store, broadcast: Callable[[dict], None] | None = None,
                 evidence: Callable[[int, str, float], None] | None = None):
        self.store = store
        self.broadcast = broadcast or (lambda msg: None)
        self.evidence = evidence or (lambda iid, cam, ts: None)
        self.lock = threading.RLock()
        self.open: dict[int, dict] = {}  # incident id -> live state
        self.cam_area: dict[str, str] = {}
        self.cam_name: dict[str, str] = {}
        self._last_push: dict[int, float] = {}

    def set_camera(self, cam: dict) -> None:
        self.cam_area[cam["id"]] = cam.get("area") or cam["id"]
        self.cam_name[cam["id"]] = cam.get("name") or cam["id"]

    # ------------------------------------------------------------------ events in
    @staticmethod
    def _same_event(pc: dict, c: Candidate) -> bool:
        """Same ongoing thing on one camera. Bags are matched by where they sit, because a
        bag gets a new key whenever the engine loses and re-finds it."""
        if pc["key"] == c.key or c.type != "baggage":
            return True
        a, b = pc.get("box"), c.box
        if not a or not b:
            return False
        dx, dy = (a[0] + a[2] - b[0] - b[2]) / 2, (a[1] + a[3] - b[1] - b[3]) / 2
        return (dx * dx + dy * dy) ** 0.5 < max(a[2] - a[0], a[3] - a[1], 20)

    def _find(self, c: Candidate) -> dict | None:
        area = self.cam_area.get(c.camera_id, c.camera_id)
        for st in self.open.values():
            if st["type"] != c.type:
                continue
            gap = c.ts - st["last_ts"]
            pc = st["per_cam"].get(c.camera_id)
            if pc is not None and self._same_event(pc, c):
                # Same camera, same event. While the operator has not acted on it (or has
                # dismissed it), keep updating that incident instead of raising a duplicate.
                if gap <= config.MERGE_WINDOW_S or (st["status"] != "confirmed" and gap <= config.REOPEN_WINDOW_S):
                    return st
                continue
            if pc is not None:
                continue  # a different bag on the same camera is a different incident
            if st["status"] != "dismissed" and st["area"] == area and gap <= config.MERGE_WINDOW_S:
                return st  # another camera in the same area: cross-camera merge
        return None

    def ingest(self, c: Candidate) -> dict:
        """Called for every candidate the false-alarm filter lets through."""
        with self.lock:
            self._prune(c.ts)
            st = self._find(c)
            created = st is None
            if created:
                st = {"id": 0, "type": c.type, "subtype": c.subtype, "status": "new",
                      "area": self.cam_area.get(c.camera_id, c.camera_id),
                      "first_ts": c.ts, "last_ts": c.ts, "per_cam": {}, "details": {},
                      "timeline": [], "severity": "", "score": 0.0, "wall_first": time.time()}
            new_cam = c.camera_id not in st["per_cam"]
            if not created and c.camera_id in st.get("restarted", ()):
                st["restarted"].discard(c.camera_id)
                st["first_ts"] = c.ts  # the clip looped: the same footage is not "still going"
            reseen = not created and c.ts - st["last_ts"] > config.MERGE_WINDOW_S
            if reseen:
                # seen again after a quiet gap: same incident, but duration starts over
                st["timeline"].append({"t": time.time(), "text":
                                       f"Seen again on {self.cam_name.get(c.camera_id, c.camera_id)} "
                                       f"after {c.ts - st['last_ts']:.0f}s"})
                st["first_ts"] = c.ts
            pc = st["per_cam"].setdefault(c.camera_id, {"key": c.key, "conf": 0.0, "first_ts": c.ts})
            pc["conf"] = max(pc["conf"] * 0.98, c.conf)  # slow decay so one spike does not stick forever
            pc["last_ts"], pc["box"] = c.ts, c.box
            st["last_ts"] = c.ts
            st["wall_last"] = time.time()
            if c.subtype == "abandoned" or not st["subtype"]:
                st["subtype"] = c.subtype
            for k, v in c.details.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and k in st["details"] \
                        and k in {"people", "vehicles", "people_nearby", "owner_away_s", "stationary_s", "model_conf"}:
                    st["details"][k] = max(st["details"][k], v)
                else:
                    st["details"][k] = v

            miss = 1.0
            for v in st["per_cam"].values():
                miss *= 1 - min(v["conf"], 0.99)
            conf = 1 - miss
            prev_level = st["severity"]
            score, lvl, reasons = score_incident(st["type"], st["subtype"], conf,
                                                 st["last_ts"] - st["first_ts"], len(st["per_cam"]),
                                                 st["details"])
            if score < st["score"]:
                # severity never falls while the incident is open; keep the score together
                # with the reasons that produced it, so the two always add up
                score, reasons = st["score"], st["reasons"]
            lvl = level(score)
            st.update(confidence=conf, score=score, severity=lvl, reasons=reasons)

            now_wall = time.time()
            if created:
                st["timeline"].append({"t": now_wall, "text":
                                       f"Detected on {self.cam_name.get(c.camera_id, c.camera_id)}"})
                st["id"] = self.store.insert_incident(self._row(st))
                self.open[st["id"]] = st
                self.evidence(st["id"], c.camera_id, c.ts)
            else:
                if new_cam:
                    st["timeline"].append({"t": now_wall, "text":
                                           f"Also seen on {self.cam_name.get(c.camera_id, c.camera_id)}: merged"})
                if prev_level and lvl != prev_level:
                    st["timeline"].append({"t": now_wall, "text": f"Severity raised {prev_level} to {lvl}"})
            changed = created or new_cam or reseen or lvl != prev_level
            if changed or now_wall - self._last_push.get(st["id"], 0) > 2.0:
                self._last_push[st["id"]] = now_wall
                self.store.update_incident(st["id"], **{k: v for k, v in self._row(st).items()
                                                        if k not in {"keyframe", "clip", "verification"}})
                kind = "incident.new" if created else "incident.update"
                self.broadcast({"type": kind, "incident": self.store.incident(st["id"]),
                                "alert": created or (lvl != prev_level and lvl in {"Critical", "High"})})
            return st

    def _row(self, st: dict) -> dict:
        return {"type": st["type"], "subtype": st["subtype"], "status": st["status"],
                "severity": st["severity"], "score": st["score"], "confidence": st.get("confidence", 0),
                "reasons": st.get("reasons", []),
                "cameras": [{"id": k, "name": self.cam_name.get(k, k), "confidence": round(v["conf"], 3)}
                            for k, v in st["per_cam"].items()],
                "area": st["area"], "first_ts": st["wall_first"],
                "last_ts": st.get("wall_last", st["wall_first"]),
                "details": {k: v for k, v in st["details"].items() if k != "rule_box"},
                "timeline": st["timeline"]}

    def camera_restarted(self, camera_id: str) -> None:
        """A looping file source started over. Open incidents on that camera keep their
        identity but their duration starts again when the event is next seen."""
        with self.lock:
            for st in self.open.values():
                if camera_id in st["per_cam"]:
                    st.setdefault("restarted", set()).add(camera_id)

    def _prune(self, ts: float) -> None:
        for iid in [i for i, s in self.open.items() if ts - s["last_ts"] > config.REOPEN_WINDOW_S
                    or ts < s["last_ts"] - 5]:  # ts going backwards: an offline clip restarted
            del self.open[iid]

    def active_in_area(self, camera_id: str, typ: str, ts: float) -> bool:
        area = self.cam_area.get(camera_id, camera_id)
        with self.lock:
            return any(s["type"] == typ and s["area"] == area and camera_id not in s["per_cam"]
                       and s["status"] != "dismissed" and abs(ts - s["last_ts"]) < config.GROUP_GAP_S
                       for s in self.open.values())

    # ------------------------------------------------------------------ operator feedback
    def feedback(self, iid: int, action: str) -> dict | None:
        inc = self.store.incident(iid)
        if not inc:
            return None
        status = "confirmed" if action == "confirm" else "dismissed"
        step = -config.CONFIRM_STEP if action == "confirm" else config.DISMISS_STEP
        text = "Confirmed by operator" if action == "confirm" else "Dismissed by operator"
        with self.lock:
            changes = []
            for cam in inc["cameras"] or []:
                old = self.store.threshold_adj(cam["id"], inc["type"])
                new = round(min(config.MAX_ADJ, max(0.0, old + step)), 3)
                self.store.set_threshold_adj(cam["id"], inc["type"], new)
                self.store.x("INSERT INTO feedback(ts,incident_id,action,camera_id,type,threshold_adj,keyframe)"
                             " VALUES(?,?,?,?,?,?,?)",
                             (time.time(), iid, action, cam["id"], inc["type"], new, inc.get("keyframe")))
                if new != old:
                    gate = config.GATE[inc["type"]]
                    changes.append(f"{cam['name']} {inc['type']} gate {gate + old:.2f} to {gate + new:.2f}")
            timeline = (inc["timeline"] or []) + [{"t": time.time(), "text": text + (
                ". " + "; ".join(changes) if changes else "")}]
            self.store.update_incident(iid, status=status, timeline=timeline)
            if iid in self.open:
                self.open[iid]["status"] = status
                self.open[iid]["timeline"] = timeline
        inc = self.store.incident(iid)
        self.broadcast({"type": "incident.update", "incident": inc, "alert": False})
        return inc
