"""SQLite store. One connection guarded by a lock; every write is a short transaction."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS cameras(
  id TEXT PRIMARY KEY, name TEXT, source TEXT, kind TEXT, area TEXT, profile TEXT, created REAL);
CREATE TABLE IF NOT EXISTS zones(
  id INTEGER PRIMARY KEY AUTOINCREMENT, camera_id TEXT, name TEXT, kind TEXT, points TEXT);
CREATE TABLE IF NOT EXISTS incidents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, subtype TEXT, status TEXT, severity TEXT,
  score REAL, confidence REAL, reasons TEXT, cameras TEXT, area TEXT, first_ts REAL, last_ts REAL,
  details TEXT, keyframe TEXT, clip TEXT, verification TEXT, timeline TEXT);
CREATE TABLE IF NOT EXISTS suppressed(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, camera_id TEXT, type TEXT, reason TEXT,
  conf REAL, duration REAL);
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, incident_id INTEGER, action TEXT,
  camera_id TEXT, type TEXT, threshold_adj REAL, keyframe TEXT);
CREATE TABLE IF NOT EXISTS thresholds(
  camera_id TEXT, type TEXT, adj REAL, PRIMARY KEY(camera_id, type));
CREATE TABLE IF NOT EXISTS fps_log(ts REAL, camera_id TEXT, fps REAL, latency_ms REAL);
"""

JSON_COLS = {"reasons", "cameras", "details", "verification", "timeline", "points"}


class Store:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def _row(self, r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        for k in JSON_COLS & d.keys():
            d[k] = json.loads(d[k]) if d[k] else None
        return d

    def q(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self.lock:
            return [self._row(r) for r in self.conn.execute(sql, args).fetchall()]

    def x(self, sql: str, args: tuple = ()) -> int:
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid or 0

    # ---- cameras
    def cameras(self) -> list[dict]:
        return self.q("SELECT * FROM cameras ORDER BY created")

    def add_camera(self, cam: dict) -> None:
        self.x("INSERT OR REPLACE INTO cameras VALUES(?,?,?,?,?,?,?)",
               (cam["id"], cam["name"], cam["source"], cam["kind"], cam["area"], cam["profile"],
                time.time()))

    def remove_camera(self, cid: str) -> None:
        self.x("DELETE FROM cameras WHERE id=?", (cid,))
        self.x("DELETE FROM zones WHERE camera_id=?", (cid,))

    # ---- zones
    def zones(self, camera_id: str | None = None) -> list[dict]:
        if camera_id:
            return self.q("SELECT * FROM zones WHERE camera_id=?", (camera_id,))
        return self.q("SELECT * FROM zones")

    def add_zone(self, camera_id: str, name: str, kind: str, points: list) -> int:
        return self.x("INSERT INTO zones(camera_id,name,kind,points) VALUES(?,?,?,?)",
                      (camera_id, name, kind, json.dumps(points)))

    # ---- incidents
    def insert_incident(self, inc: dict) -> int:
        cols = ["type", "subtype", "status", "severity", "score", "confidence", "reasons",
                "cameras", "area", "first_ts", "last_ts", "details", "keyframe", "clip",
                "verification", "timeline"]
        vals = [json.dumps(inc.get(c)) if c in JSON_COLS else inc.get(c) for c in cols]
        return self.x(f"INSERT INTO incidents({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                      tuple(vals))

    def update_incident(self, iid: int, **fields: Any) -> None:
        if not fields:
            return
        sets = ",".join(f"{k}=?" for k in fields)
        vals = [json.dumps(v) if k in JSON_COLS else v for k, v in fields.items()]
        self.x(f"UPDATE incidents SET {sets} WHERE id=?", (*vals, iid))

    def incident(self, iid: int) -> dict | None:
        rows = self.q("SELECT * FROM incidents WHERE id=?", (iid,))
        return rows[0] if rows else None

    def incidents(self, status: str | None = None, limit: int = 200) -> list[dict]:
        if status:
            return self.q("SELECT * FROM incidents WHERE status=? ORDER BY score DESC, last_ts DESC "
                          "LIMIT ?", (status, limit))
        return self.q("SELECT * FROM incidents ORDER BY last_ts DESC LIMIT ?", (limit,))

    # ---- thresholds learned from operator feedback
    def threshold_adj(self, camera_id: str, typ: str) -> float:
        rows = self.q("SELECT adj FROM thresholds WHERE camera_id=? AND type=?", (camera_id, typ))
        return rows[0]["adj"] if rows else 0.0

    def set_threshold_adj(self, camera_id: str, typ: str, adj: float) -> None:
        self.x("INSERT OR REPLACE INTO thresholds VALUES(?,?,?)", (camera_id, typ, adj))
