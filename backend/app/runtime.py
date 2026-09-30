"""Per-camera pipeline and worker threads.

Pipeline   one camera's detect -> track -> engines -> filter -> incidents -> annotate chain.
           No threads and no clock of its own, so the same code runs live, in demo replay
           and in the offline evaluation scripts.
Worker     one thread per camera: reads RTSP (auto-reconnect) or a looping file, samples
           about TARGET_FPS frames a second and feeds the pipeline.
Runtime    shared models, store, filter and incident manager.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
import cv2  # noqa: E402
import numpy as np  # noqa: E402

from . import config, verify  # noqa: E402
from .db import Store  # noqa: E402
from .aux_models import get_models, get_scheduler  # noqa: E402
from .detector import Tracker, get_detector  # noqa: E402
from .engines.accident import AccidentEngine  # noqa: E402
from .engines.baggage import BaggageEngine  # noqa: E402
from .engines.crowd import CrowdEngine  # noqa: E402
from .engines.extra import (FireEngine, HazardEngine, MedicalEngine, SecurityEngine,  # noqa: E402
                            ViolenceEngine, WeaponEngine)
from .intel.filter import FalseAlarmFilter  # noqa: E402
from .intel.incidents import IncidentManager  # noqa: E402
from .schema import Candidate, Frame, Track  # noqa: E402

log = logging.getLogger("drishti.runtime")

COLORS = {"person": (214, 160, 84), "vehicle": (170, 176, 184), "bag": (52, 176, 236)}
RED = (68, 68, 239)
ZONE_COLORS = {"lane": (160, 160, 160), "restricted": (68, 68, 239), "crowd": (214, 160, 84),
               "ignore": (110, 110, 110)}
BAG_IDS = [k for k, v in config.COCO.items() if v in config.BAGS]
ALL_TYPES = ("accident", "crowd", "baggage", "fire", "weapon", "violence", "medical", "hazard", "security")
# "all" is the default: every engine on every camera. The narrower profiles remain for
# machines that cannot afford all models on every stream.
PROFILES = {"all": ALL_TYPES, "mixed": ALL_TYPES,
            "traffic": ("accident", "fire", "medical", "hazard", "security"),
            "public": ("crowd", "baggage", "fire", "weapon", "violence", "medical", "hazard", "security")}
ENGINES = {"accident": AccidentEngine, "crowd": CrowdEngine, "baggage": BaggageEngine, "fire": FireEngine,
           "weapon": WeaponEngine, "violence": ViolenceEngine, "medical": MedicalEngine,
           "hazard": HazardEngine, "security": SecurityEngine}
# which auxiliary model each incident type needs
NEEDS = {"accident": {"accident"}, "fire": {"fire", "scene"}, "weapon": {"weapon", "violence", "scene"},
         "violence": {"violence", "scene", "weapon"}, "medical": {"fall", "scene"}, "hazard": {"scene"}}


class Runtime:
    def __init__(self, store: Store, broadcast: Callable[[dict], None] | None = None,
                 live: bool = True, use_models: bool = True):
        self.store = store
        self.live = live
        self.use_models = use_models
        self.broadcast = broadcast or (lambda m: None)
        self.lock = threading.Lock()
        self.pipelines: dict[str, "Pipeline"] = {}
        self.incidents = IncidentManager(store, self.broadcast, self._evidence)
        self.filter = FalseAlarmFilter(store.threshold_adj, self._suppressed,
                                       self.incidents.active_in_area)
        self.suppressed: list[dict] = []
        self.history: list[dict] = []  # confirmed events in stream time, for evaluation
        self._zones: dict[str, list[dict]] = {}
        self.reload_zones()

    def reload_zones(self) -> None:
        z: dict[str, list[dict]] = {}
        for row in self.store.zones():
            z.setdefault(row["camera_id"], []).append(row)
        self._zones = z

    def zones(self, camera_id: str) -> list[dict]:
        return self._zones.get(camera_id, [])

    def _suppressed(self, row: dict) -> None:
        self.suppressed.append(row)
        if self.live:
            self.store.x("INSERT INTO suppressed(ts,camera_id,type,reason,conf,duration) VALUES(?,?,?,?,?,?)",
                         (time.time(), row["camera_id"], row["type"], row["reason"], row["conf"],
                          row["duration"]))
            self.broadcast({"type": "suppressed", "row": row})

    def _evidence(self, iid: int, camera_id: str, ts: float) -> None:
        p = self.pipelines.get(camera_id)
        if p is not None and self.live:
            p.want_evidence.append((iid, ts))

    def handle(self, frame: Frame, cands: list[Candidate]) -> list[Candidate]:
        with self.lock:
            confirmed = self.filter.process(frame, cands)
            for c in confirmed:
                st = self.incidents.ingest(c)
                if not any(h["id"] == st["id"] for h in self.history):
                    self.history.append({"id": st["id"], "type": c.type, "camera_id": c.camera_id,
                                         "ts": c.ts, "subtype": c.subtype})
            return confirmed


class Pipeline:
    def __init__(self, cam: dict, rt: Runtime, fps: float = config.TARGET_FPS,
                 cache: dict | None = None, record: bool = False):
        self.cam, self.rt, self.fps = cam, rt, fps
        self.id = cam["id"]
        self.kinds = PROFILES.get(cam.get("profile", "all"), PROFILES["all"])
        self.cache = cache  # demo replay: frame index -> cached tracks and model outputs
        self.record: dict[str, dict] | None = {} if record else None
        self.detector = get_detector() if (cache is None and rt.use_models) else None
        needed = set().union(*(NEEDS.get(k, set()) for k in self.kinds))
        models = get_models() if (cache is None and rt.use_models) else {}
        self.aux = {k: m for k, m in models.items() if k in needed and m.available}
        self.ring: deque = deque()
        self.want_evidence: list[tuple[int, float]] = []
        self._clips_due: list[tuple[int, float]] = []
        self.latest: tuple[int, bytes] | None = None
        self.raw_latest: np.ndarray | None = None
        self.last_prob = 0.0
        self.reset()
        rt.pipelines[self.id] = self
        rt.incidents.set_camera(cam)

    def reset(self) -> None:
        self.n = 0
        self.tracks: list[Track] = []
        self.tracker = Tracker(self.fps / config.DETECT_EVERY) if self.cache is None and self.rt.use_models else None
        self.engines = []
        for k in self.kinds:
            if k == "accident":
                self.engines.append(AccidentEngine(self.id, self.cache is not None or "accident" in self.aux))
            else:
                self.engines.append(ENGINES[k](self.id))
        self.last_aux: dict[str, float] = {}
        self.active_boxes: list[tuple] = []

    def process(self, image: np.ndarray, ts: float, frame_idx: int | None = None) -> bytes:
        self.n += 1
        fresh = False
        aux: dict[str, dict] = {}
        if self.cache is not None:
            rec = self.cache.get(str(frame_idx))
            if rec is not None:
                fresh = rec["fresh"]
                if fresh:
                    self.tracks = [Track(t[0], t[1], tuple(t[2:6]), t[6]) for t in rec["tracks"]]
                aux = dict(rec.get("aux") or {})
                if rec.get("acc") is not None:  # caches written before the extra models existed
                    aux["accident"] = {"dets": rec["acc"]}
        else:
            fresh = self.n % config.DETECT_EVERY == 1 or config.DETECT_EVERY == 1
            if fresh:
                boxes = self.detector.detect(image)
                is_bag = np.isin(boxes.cls.astype(int), BAG_IDS)
                # People and vehicles go through ByteTrack. Bags do not: a parked bag is often a
                # weak detection, so the baggage engine keeps its own position-based memory.
                moving = self.tracker.update(boxes[~is_bag], image)
                bags = [Track(0, config.COCO[int(c)], tuple(float(v) for v in b), float(p))
                        for b, c, p in zip(boxes.xyxy[is_bag], boxes.cls[is_bag], boxes.conf[is_bag])]
                self.tracks = [t for t in moving if t.cls not in config.BAGS] + bags
            if self.aux:
                if self.rt.live:  # off the frame loop: results arrive a little later
                    sched = get_scheduler()
                    sched.offer(self.id, image, ts)
                    aux = {k: v for k, v in sched.take(self.id).items() if k in self.aux}
                else:  # offline: call each model directly at its cadence
                    for name, m in self.aux.items():
                        if ts - self.last_aux.get(name, -1e9) >= m.every_s:
                            self.last_aux[name] = ts
                            aux[name] = m.run(image)
            if self.record is not None and frame_idx is not None:
                self.record[str(frame_idx)] = {
                    "fresh": fresh, "aux": aux or None,
                    "tracks": [[t.id, t.cls, *[round(v, 1) for v in t.box], round(t.conf, 3)]
                               for t in self.tracks] if fresh else []}

        frame = Frame(self.id, ts, image, self.tracks, fresh, aux, self.rt.zones(self.id))
        cands: list[Candidate] = []
        for e in self.engines:
            cands += e.process(frame)
            if isinstance(e, CrowdEngine):
                self.last_prob = e.last_prob
        confirmed = self.rt.handle(frame, cands)
        if confirmed or fresh:
            keep = [b for b in self.active_boxes if ts - b[2] < 2.0 and not any(c.type == b[0] for c in confirmed)]
            self.active_boxes = keep + [(c.type, c.box, ts, c.subtype) for c in confirmed if c.box]
        if not self.rt.live:
            return b""
        self.raw_latest = image
        jpeg, people = self._annotate(image, ts)
        self.ring.append((ts, jpeg, people))
        while self.ring and ts - self.ring[0][0] > config.RING_SECONDS + 5:
            self.ring.popleft()
        self.latest = (self.n, jpeg)
        self._evidence(ts, jpeg)
        return jpeg

    # ------------------------------------------------------------------ drawing
    def _annotate(self, image: np.ndarray, ts: float) -> tuple[bytes, list]:
        h, w = image.shape[:2]
        s = config.STREAM_WIDTH / w
        img = cv2.resize(image, (config.STREAM_WIDTH, int(round(h * s))), interpolation=cv2.INTER_LINEAR)
        hh = img.shape[0]
        for z in self.rt.zones(self.id):
            pts = np.array([[p[0] * config.STREAM_WIDTH, p[1] * hh] for p in z["points"]], np.int32)
            cv2.polylines(img, [pts], True, ZONE_COLORS.get(z["kind"], (150, 150, 150)), 1, cv2.LINE_AA)
        for t in self.tracks:
            fam = "person" if t.cls == "person" else "bag" if t.cls in config.BAGS else "vehicle"
            self._box(img, t.box, s, COLORS[fam], f"{t.cls} {t.id}" if t.id else t.cls)
        for typ, box, _, sub in self.active_boxes:
            self._box(img, box, s, RED, f"{typ.upper()} {sub}".strip(), 2)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])
        people = [tuple(v * s for v in t.box) for t in self.tracks if t.cls == "person"]
        return buf.tobytes(), people

    @staticmethod
    def _box(img: np.ndarray, box, s: float, color, label: str, thick: int = 1) -> None:
        x1, y1, x2, y2 = (int(v * s) for v in box)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thick, cv2.LINE_AA)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        y = max(y1, th + 4)
        cv2.rectangle(img, (x1, y - th - 4), (x1 + tw + 6, y), color, -1)
        cv2.putText(img, label, (x1 + 3, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (12, 14, 18), 1, cv2.LINE_AA)

    # ------------------------------------------------------------------ evidence
    def _evidence(self, ts: float, jpeg: bytes) -> None:
        while self.want_evidence:
            iid, t0 = self.want_evidence.pop()
            name = f"{iid}.jpg"
            (config.MEDIA / "keyframes" / name).write_bytes(jpeg)
            self.rt.store.update_incident(iid, keyframe=f"/media/keyframes/{name}")
            self._clips_due.append((iid, ts + 4.0))
        due = [d for d in self._clips_due if ts >= d[1]]
        self._clips_due = [d for d in self._clips_due if ts < d[1]]
        for iid, _ in due:
            frames = [r[1] for r in self.ring]
            if verify.enabled():  # three frames spread over the evidence window, heads blurred
                picks = [self.ring[i] for i in sorted({0, len(self.ring) // 2, len(self.ring) - 1})]
                verify.verify_async(self.rt.store, self.rt.broadcast, iid, [(r[1], r[2]) for r in picks])
            span = self.ring[-1][0] - self.ring[0][0] if len(self.ring) > 1 else 1.0
            fps = max(2.0, len(frames) / max(span, 0.5))
            threading.Thread(target=self._write_clip, args=(iid, frames, fps), daemon=True).start()

    def _write_clip(self, iid: int, frames: list[bytes], fps: float) -> None:
        out = config.MEDIA / "clips" / f"{iid}.mp4"
        try:
            p = subprocess.Popen(
                [str(config.FFMPEG), "-v", "error", "-y", "-f", "image2pipe", "-framerate", f"{fps:.2f}",
                 "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                 "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-movflags", "+faststart",
                 str(out)], stdin=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            p.communicate(b"".join(frames), timeout=60)
            if out.exists() and out.stat().st_size > 0:
                self.rt.store.update_incident(iid, clip=f"/media/clips/{out.name}")
                self.rt.broadcast({"type": "incident.update", "incident": self.rt.store.incident(iid),
                                   "alert": False})
        except Exception:  # noqa: BLE001
            log.exception("evidence clip for incident %s failed", iid)


class Worker(threading.Thread):
    """Reads one camera and drives its pipeline."""

    def __init__(self, cam: dict, rt: Runtime, cache: dict | None = None):
        super().__init__(daemon=True, name=f"cam-{cam['id']}")
        self.cam, self.rt = cam, rt
        self.pipeline = Pipeline(cam, rt, cache=cache)
        self.stop_flag = threading.Event()
        self.status = "connecting"
        self.fps = 0.0
        self.latency_ms = 0.0
        self.frames = 0
        self.error = ""
        self._times: deque = deque(maxlen=60)
        self._last_log = time.time()

    def stop(self) -> None:
        self.stop_flag.set()

    def run(self) -> None:
        is_file = self.cam["kind"] == "file"
        while not self.stop_flag.is_set():
            try:
                (self._run_file if is_file else self._run_rtsp)()
            except Exception as e:  # noqa: BLE001
                log.exception("camera %s crashed", self.cam["id"])
                self.error = repr(e)
            if self.stop_flag.is_set():
                break
            self.status = "reconnecting"
            self.stop_flag.wait(2.0)

    def _tick(self, image: np.ndarray, ts: float, idx: int | None) -> None:
        t0 = time.perf_counter()
        self.pipeline.process(image, ts, idx)
        dt = time.perf_counter() - t0
        self.latency_ms = 0.8 * self.latency_ms + 0.2 * dt * 1000 if self.latency_ms else dt * 1000
        now = time.time()
        self._times.append(now)
        self.frames += 1
        if len(self._times) > 1:
            self.fps = (len(self._times) - 1) / max(self._times[-1] - self._times[0], 1e-3)
        self.status = "online"
        if now - self._last_log > 10:
            self._last_log = now
            self.rt.store.x("INSERT INTO fps_log VALUES(?,?,?,?)",
                            (now, self.cam["id"], round(self.fps, 2), round(self.latency_ms, 1)))
            log.info("%s %.1f fps, %.0f ms/frame", self.cam["id"], self.fps, self.latency_ms)

    def _run_file(self) -> None:
        path = self.cam["source"]
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            self.status, self.error = "offline", f"cannot open {Path(path).name}"
            self.stop_flag.wait(5)
            return
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, round(src_fps / config.TARGET_FPS))
        self.pipeline.fps = src_fps / step
        self.pipeline.reset()
        start, idx = time.time(), -1
        while not self.stop_flag.is_set():
            target = int((time.time() - start) * src_fps)
            target -= target % step
            if target <= idx:
                time.sleep(0.004)
                continue
            ok = True
            while idx < target - 1 and ok:  # skip frames we are too late for
                ok = cap.grab()
                idx += 1
            ok, image = cap.read() if ok else (False, None)
            idx += 1
            if not ok:  # end of file: loop from the start with fresh engine state
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                start, idx = time.time(), -1
                self.pipeline.reset()
                self.rt.incidents.camera_restarted(self.cam["id"])
                continue
            self._tick(image, start + idx / src_fps, idx)
        cap.release()

    def _run_rtsp(self) -> None:
        cap = cv2.VideoCapture(self.cam["source"], cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self.status, self.error = "offline", "stream not reachable"
            return
        self.error = ""
        self.pipeline.fps = config.TARGET_FPS
        self.pipeline.reset()
        latest: list = [None]
        alive = threading.Event()
        alive.set()

        def reader() -> None:
            while alive.is_set() and not self.stop_flag.is_set():
                ok, img = cap.read()
                if not ok:
                    alive.clear()
                    break
                latest[0] = (time.time(), img)

        threading.Thread(target=reader, daemon=True).start()
        period, last_ts = 1.0 / config.TARGET_FPS, 0.0
        stale_since = time.time()
        while alive.is_set() and not self.stop_flag.is_set():
            t0 = time.time()
            item = latest[0]
            if item is None or item[0] == last_ts:
                if time.time() - stale_since > 8:
                    break  # no new frames: reconnect
                time.sleep(0.005)
                continue
            last_ts = stale_since = item[0]
            self._tick(item[1], item[0], None)
            time.sleep(max(0.0, period - (time.time() - t0)))
        alive.clear()
        cap.release()


def load_cache(cam_id: str) -> dict | None:
    p = config.DEMO / "cache" / f"{cam_id}.json"
    return json.loads(p.read_text()) if p.exists() else None
