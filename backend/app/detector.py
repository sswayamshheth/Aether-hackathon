"""Model wrappers. One shared detector and one shared accident model serve every camera;
a lock keeps CPU inference serial so four streams do not fight over the same cores.
Tracking state is per camera (one ByteTrack instance each).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

from . import config
from .schema import Track

log = logging.getLogger("drishti.detector")
_infer_lock = threading.Lock()


def _resolve(name: str) -> tuple[str, str]:
    """Prefer an exported OpenVINO model, fall back to the .pt file."""
    ov = config.MODELS / f"{name}_openvino_model"
    if ov.exists():
        return str(ov), "OpenVINO (CPU)"
    pt = config.MODELS / f"{name}.pt"
    return (str(pt) if pt.exists() else f"{name}.pt"), "PyTorch (CPU)"


class Detector:
    """COCO detector restricted to people, vehicles and bags."""

    def __init__(self) -> None:
        from ultralytics import YOLO

        path, self.backend = _resolve(config.DETECTOR_WEIGHTS)
        self.model = YOLO(path, task="detect")
        self.classes = sorted(config.COCO)
        self.name = f"{config.DETECTOR_WEIGHTS} COCO"
        log.info("detector %s via %s", path, self.backend)

    def detect(self, image: np.ndarray):
        """Returns an Ultralytics Boxes object (numpy) for the tracker."""
        with _infer_lock:
            r = self.model.predict(image, imgsz=config.DETECTOR_IMGSZ, conf=0.12,
                                   classes=self.classes, verbose=False)[0]
        return r.boxes.cpu().numpy()


class AccidentModel:
    """Fine-tuned accident detector. `available` is False when no weights are present,
    in which case the accident engine runs on its trajectory rule alone."""

    def __init__(self) -> None:
        self.available = False
        self.names: dict[int, str] = {}
        self.backend = ""
        self._lock = threading.Lock()
        p = Path(config.ACCIDENT_WEIGHTS)
        ov = p.with_name(p.stem + "_openvino_model")
        path = ov if ov.exists() else p
        if not path.exists():
            log.warning("no accident weights at %s, accident engine uses the rule fallback", p)
            return
        from ultralytics import YOLO

        self.model = YOLO(str(path), task="detect")
        self.backend = "OpenVINO (CPU)" if path.is_dir() else "PyTorch (CPU)"
        self.names = dict(self.model.names)
        self.available = True
        log.info("accident model %s via %s, classes %s", path, self.backend, self.names)

    def detect(self, image: np.ndarray) -> list[dict]:
        with self._lock:
            r = self.model.predict(image, imgsz=config.ACCIDENT_IMGSZ, conf=0.25, verbose=False)[0]
        return [{"cls": self.names[int(c)], "conf": float(p), "box": tuple(map(float, b))}
                for b, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist())]


class Tracker:
    """ByteTrack (Ultralytics implementation), one instance per camera."""

    def __init__(self, fps: float) -> None:
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.utils import IterableSimpleNamespace, YAML
        from ultralytics.utils.checks import check_yaml

        cfg = IterableSimpleNamespace(**YAML.load(check_yaml("bytetrack.yaml")))
        cfg.track_buffer = 40  # frames a lost track is kept; detection runs at about fps/2
        self.fps = fps
        from ultralytics.trackers.basetrack import BaseTrack

        count = BaseTrack._count  # constructing a tracker resets the shared ID counter
        self._bt = BYTETracker(args=cfg)
        BaseTrack._count = count  # keep IDs unique across cameras and across clip loops

    def update(self, boxes, image: np.ndarray) -> list[Track]:
        rows = self._bt.update(boxes, image)
        out = []
        for r in rows:
            cls = config.COCO.get(int(r[6]))
            if cls:
                out.append(Track(int(r[4]), cls, (float(r[0]), float(r[1]), float(r[2]), float(r[3])),
                                 float(r[5])))
        return out


class AccidentService:
    """Runs the accident model on its own thread so a slow model never stalls the frame
    loop. Each camera has at most one frame waiting; results come back a little late and
    are picked up with poll(). Offline evaluation calls the model directly instead."""

    def __init__(self, model: AccidentModel) -> None:
        self.model = model
        self.pending: dict[str, tuple[np.ndarray, float]] = {}
        self.working: str | None = None
        self.results: dict[str, tuple[list[dict], float]] = {}
        self.cv = threading.Condition()
        self.last_ms = 0.0
        threading.Thread(target=self._loop, daemon=True, name="accident-model").start()

    def busy(self, cam: str) -> bool:
        return cam in self.pending or self.working == cam

    def submit(self, cam: str, image: np.ndarray, ts: float) -> None:
        with self.cv:
            self.pending[cam] = (image.copy(), ts)
            self.cv.notify()

    def poll(self, cam: str) -> tuple[list[dict], float] | None:
        return self.results.pop(cam, None)

    def _loop(self) -> None:
        import time

        while True:
            with self.cv:
                while not self.pending:
                    self.cv.wait()
                cam = min(self.pending, key=lambda k: self.pending[k][1])  # oldest first
                image, ts = self.pending.pop(cam)
                self.working = cam
            t0 = time.perf_counter()
            try:
                dets = self.model.detect(image)
            except Exception:  # noqa: BLE001
                log.exception("accident model failed")
                dets = []
            self.last_ms = (time.perf_counter() - t0) * 1000
            self.results[cam] = (dets, ts)
            self.working = None


_service: AccidentService | None = None


def get_accident_service() -> AccidentService:
    global _service
    model = get_accident_model()
    with _load_lock:
        if _service is None:
            _service = AccidentService(model)
    return _service


_detector: Detector | None = None
_accident: AccidentModel | None = None
_load_lock = threading.Lock()


def get_detector() -> Detector:
    global _detector
    with _load_lock:
        if _detector is None:
            _detector = Detector()
    return _detector


def get_accident_model() -> AccidentModel:
    global _accident
    with _load_lock:
        if _accident is None:
            _accident = AccidentModel()
    return _accident
