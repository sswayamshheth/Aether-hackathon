"""Drishti API: cameras, live video, incidents, zones, analytics, model metrics."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import alerts, config
from .db import Store
from .runtime import Runtime, Worker, load_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("drishti.api")


class Hub:
    """Fan-out of JSON events from worker threads to dashboard WebSockets."""

    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def publish(self, msg: dict) -> None:
        if self.loop and self.clients:
            asyncio.run_coroutine_threadsafe(self._send(msg), self.loop)
        if msg.get("alert") and msg.get("incident"):
            alerts.dispatch(msg["incident"])

    async def _send(self, msg: dict) -> None:
        data = json.dumps(msg, default=str)
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001
                self.clients.discard(ws)


class State:
    store: Store
    rt: Runtime
    hub = Hub()
    workers: dict[str, Worker] = {}
    started = time.time()


S = State()


def start_worker(cam: dict) -> None:
    cache = load_cache(cam["id"]) if config.DEMO_MODE else None
    w = Worker(cam, S.rt, cache=cache)
    S.workers[cam["id"]] = w
    w.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    S.hub.loop = asyncio.get_running_loop()
    db = config.DEMO / "demo.db" if config.DEMO_MODE else config.DB_PATH
    if config.DEMO_MODE and db.exists():
        db.unlink()  # demo mode always starts from a clean incident queue
    S.store = Store(db)
    S.rt = Runtime(S.store, S.hub.publish, live=True)
    alerts.configure(S.store)
    seed_mode = "file" if config.DEMO_MODE else os.environ.get("DRISHTI_SEED", "")
    if seed_mode in {"file", "rtsp"}:
        # the four simulated cameras from scripts/cameras.json; cameras added in the UI are kept
        seed = json.loads((config.ROOT / "scripts" / "cameras.json").read_text())
        for c in seed["cameras"]:
            S.store.add_camera({"id": c["id"], "name": c["name"], "kind": seed_mode, "area": c["area"],
                                "profile": c["profile"],
                                "source": c["rtsp"] if seed_mode == "rtsp" else str(config.ROOT / c["clip"])})
    for cam in S.store.cameras():
        start_worker(cam)
    log.info("started with %d cameras, demo=%s", len(S.workers), config.DEMO_MODE)
    yield
    for w in S.workers.values():
        w.stop()


app = FastAPI(title="Drishti", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory=str(config.MEDIA)), name="media")


# ------------------------------------------------------------------ status
def camera_view(cam: dict) -> dict:
    w = S.workers.get(cam["id"])
    return {**cam, "status": w.status if w else "stopped", "fps": round(w.fps, 1) if w else 0,
            "latency_ms": round(w.latency_ms) if w else 0, "error": w.error if w else "",
            "frames": w.frames if w else 0,
            "source_label": Path(cam["source"]).name if cam["kind"] == "file" else cam["source"]}


def status_payload() -> dict:
    cams = [camera_view(c) for c in S.store.cameras()]
    online = [c for c in cams if c["status"] == "online"]
    active = S.store.q("SELECT COUNT(*) n FROM incidents WHERE status='new'")[0]["n"]
    det = S.rt.pipelines and next(iter(S.rt.pipelines.values())).detector
    return {"cameras_total": len(cams), "cameras_online": len(online),
            "fps_avg": round(sum(c["fps"] for c in online) / len(online), 1) if online else 0,
            "active_incidents": active, "demo": config.DEMO_MODE, "uptime_s": int(time.time() - S.started),
            "inference": "cached detections (demo replay)" if config.DEMO_MODE
            else (det.backend if det else "not loaded"),
            "vision_verify": config.VISION_VERIFY_ENABLED and bool(config.ANTHROPIC_API_KEY),
            "telegram": config.TELEGRAM_ENABLED and bool(config.TELEGRAM_TOKEN)}


@app.get("/api/status")
def status() -> dict:
    return status_payload()


# ------------------------------------------------------------------ cameras
class CameraIn(BaseModel):
    name: str
    source: str
    area: str = ""
    profile: str = "mixed"


@app.get("/api/cameras")
def cameras() -> list[dict]:
    return [camera_view(c) for c in S.store.cameras()]


def _add(name: str, source: str, kind: str, area: str, profile: str) -> dict:
    if profile not in {"traffic", "public", "mixed"}:
        raise HTTPException(422, "profile must be traffic, public or mixed")
    cam = {"id": "cam-" + uuid.uuid4().hex[:6], "name": name.strip() or "Camera", "source": source,
           "kind": kind, "area": area.strip() or name.strip() or "Unassigned", "profile": profile}
    S.store.add_camera(cam)
    start_worker(cam)
    return camera_view(cam)


@app.post("/api/cameras")
def add_camera(body: CameraIn) -> dict:
    src = body.source.strip()
    if not src.lower().startswith(("rtsp://", "rtsps://", "http://", "https://")):
        raise HTTPException(422, "source must be an rtsp:// or http(s):// stream URL")
    return _add(body.name, src, "rtsp", body.area, body.profile)


@app.post("/api/cameras/upload")
async def upload_camera(file: UploadFile = File(...), name: str = Form(""), area: str = Form(""),
                        profile: str = Form("mixed")) -> dict:
    ext = Path(file.filename or "video.mp4").suffix.lower()
    if ext not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        raise HTTPException(422, "upload an mp4, avi, mov, mkv or webm file")
    dest = config.UPLOADS / f"{uuid.uuid4().hex[:8]}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    cap = cv2.VideoCapture(str(dest))
    ok = cap.isOpened() and cap.read()[0]
    cap.release()
    if not ok:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, "that file could not be decoded as video")
    return _add(name or Path(file.filename or "Upload").stem, str(dest), "file", area, profile)


@app.delete("/api/cameras/{cid}")
def remove_camera(cid: str) -> dict:
    w = S.workers.pop(cid, None)
    if w:
        w.stop()
    S.rt.pipelines.pop(cid, None)
    S.store.remove_camera(cid)
    S.rt.reload_zones()
    return {"ok": True}


@app.get("/api/cameras/{cid}/snapshot")
def snapshot(cid: str, raw: bool = True) -> Response:
    p = S.rt.pipelines.get(cid)
    if p is None or p.raw_latest is None:
        raise HTTPException(404, "no frame yet")
    if raw:
        ok, buf = cv2.imencode(".jpg", p.raw_latest, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return Response(buf.tobytes(), media_type="image/jpeg")
    return Response(p.latest[1], media_type="image/jpeg")


@app.get("/api/cameras/{cid}/stream")
async def mjpeg(cid: str) -> StreamingResponse:
    """MJPEG fallback (the dashboard uses /ws/video)."""
    async def gen():
        last = -1
        while True:
            p = S.rt.pipelines.get(cid)
            if p is None:
                break
            if p.latest and p.latest[0] != last:
                last = p.latest[0]
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + p.latest[1] + b"\r\n"
            await asyncio.sleep(0.05)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


# ------------------------------------------------------------------ incidents
@app.get("/api/incidents")
def incidents(status: str | None = None) -> list[dict]:
    return S.store.incidents(status)


@app.get("/api/incidents/{iid}")
def incident(iid: int) -> dict:
    inc = S.store.incident(iid)
    if not inc:
        raise HTTPException(404, "incident not found")
    return inc


@app.post("/api/incidents/{iid}/{action}")
def incident_action(iid: int, action: str) -> dict:
    if action not in {"confirm", "dismiss"}:
        raise HTTPException(404, "unknown action")
    inc = S.rt.incidents.feedback(iid, action)
    if not inc:
        raise HTTPException(404, "incident not found")
    return inc


# ------------------------------------------------------------------ zones
class ZoneIn(BaseModel):
    camera_id: str
    name: str
    kind: str
    points: list[list[float]]


@app.get("/api/zones")
def zones(camera_id: str | None = None) -> list[dict]:
    return S.store.zones(camera_id)


@app.post("/api/zones")
def add_zone(z: ZoneIn) -> dict:
    if z.kind not in {"lane", "restricted", "crowd", "ignore"} or len(z.points) < 3:
        raise HTTPException(422, "a zone needs a kind and at least 3 points")
    zid = S.store.add_zone(z.camera_id, z.name.strip() or z.kind, z.kind, z.points)
    S.rt.reload_zones()
    return {"id": zid}


@app.delete("/api/zones/{zid}")
def delete_zone(zid: int) -> dict:
    S.store.x("DELETE FROM zones WHERE id=?", (zid,))
    S.rt.reload_zones()
    return {"ok": True}


# ------------------------------------------------------------------ analytics
@app.get("/api/analytics")
def analytics(minutes: int = 60) -> dict:
    now = time.time()
    since = now - minutes * 60
    bucket = 60 if minutes <= 60 else 300
    inc = S.store.q("SELECT type, severity, status, first_ts FROM incidents WHERE first_ts>=?", (since,))
    sup = S.store.q("SELECT type, reason, ts, camera_id FROM suppressed WHERE ts>=?", (since,))
    n_b = int(minutes * 60 / bucket)
    series = [{"t": since + i * bucket, "accident": 0, "crowd": 0, "baggage": 0, "suppressed": 0}
              for i in range(n_b)]
    for r in inc:
        i = min(n_b - 1, int((r["first_ts"] - since) / bucket))
        series[i][r["type"]] += 1
    for r in sup:
        i = min(n_b - 1, int((r["ts"] - since) / bucket))
        series[i]["suppressed"] += 1

    def count(rows: list[dict], key: str) -> dict:
        out: dict[str, int] = {}
        for r in rows:
            out[r[key]] = out.get(r[key], 0) + 1
        return out

    def kind(reason: str) -> str:
        return ("zone mask" if "ignore zone" in reason else "confidence gate" if "below gate" in reason
                else "persistence")

    fps = S.store.q("SELECT ts, camera_id, fps, latency_ms FROM fps_log WHERE ts>=? ORDER BY ts", (since,))
    fb = S.store.q("SELECT action, COUNT(*) n FROM feedback GROUP BY action")
    return {"bucket_s": bucket, "series": series, "by_type": count(inc, "type"),
            "by_severity": count(inc, "severity"), "by_status": count(inc, "status"),
            "incidents": len(inc), "suppressed": len(sup),
            "suppressed_by_check": count([{"k": kind(r["reason"])} for r in sup], "k"),
            "suppressed_by_type": count(sup, "type"),
            "suppressed_recent": S.store.q("SELECT * FROM suppressed ORDER BY id DESC LIMIT 12"),
            "fps": fps, "feedback": {r["action"]: r["n"] for r in fb},
            "thresholds": S.store.q("SELECT * FROM thresholds WHERE adj != 0"),
            "cameras": [camera_view(c) for c in S.store.cameras()]}


@app.get("/api/models")
def models() -> dict:
    out = {}
    for name in ("summary", "crowd_model", "inference_speed", "e2e_eval"):
        p = config.RESULTS / f"{name}.json"
        out[name] = json.loads(p.read_text()) if p.exists() else None
    return out


@app.get("/api/settings")
def settings() -> dict:
    return {"gate": config.GATE, "persist_s": config.PERSIST_S, "min_hits": config.MIN_HITS,
            "bag_unattended_s": config.BAG_UNATTENDED_S, "bag_abandoned_s": config.BAG_ABANDONED_S,
            "crowd_limit": config.CROWD_LIMIT, "merge_window_s": config.MERGE_WINDOW_S,
            "target_fps": config.TARGET_FPS, "detect_every": config.DETECT_EVERY,
            "accident_every_s": config.ACCIDENT_EVERY_S, "status": status_payload()}


# ------------------------------------------------------------------ websockets
@app.websocket("/ws")
async def ws_events(ws: WebSocket) -> None:
    await ws.accept()
    S.hub.clients.add(ws)
    try:
        while True:
            await ws.send_text(json.dumps({"type": "status", "status": status_payload(),
                                           "cameras": [camera_view(c) for c in S.store.cameras()]}))
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        S.hub.clients.discard(ws)


@app.websocket("/ws/video")
async def ws_video(ws: WebSocket) -> None:
    """Binary frames for every camera: 16-byte ASCII camera id, then a JPEG."""
    await ws.accept()
    last: dict[str, int] = {}
    try:
        while True:
            sent = False
            for cid, p in list(S.rt.pipelines.items()):
                if p.latest and last.get(cid) != p.latest[0]:
                    last[cid] = p.latest[0]
                    await ws.send_bytes(cid.encode().ljust(16)[:16] + p.latest[1])
                    sent = True
            await asyncio.sleep(0.03 if sent else 0.06)
    except (WebSocketDisconnect, RuntimeError):
        pass


# ------------------------------------------------------------------ frontend (built)
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(config.FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        f = config.FRONTEND_DIST / path
        if path and f.is_file() and config.FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
