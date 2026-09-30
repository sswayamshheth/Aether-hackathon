"""COCO detector and tracker. One shared detector serves every camera; a lock keeps
inference serial so several streams do not fight over the same cores. The other models
live in aux_models.py.
Tracking state is per camera (one ByteTrack instance each).
"""
from __future__ import annotations

import logging
import threading

import numpy as np

from . import config
from .schema import Track

log = logging.getLogger("drishti.detector")
_infer_lock = threading.Lock()


def _resolve(name: str) -> tuple[str, str, str]:
    """(weights, backend label, device). A GPU (CUDA or Apple MPS) runs the .pt file;
    on a plain CPU an exported OpenVINO model is faster when one exists."""
    from .aux_models import device

    dev = device()
    pt = config.MODELS / f"{name}.pt"
    pt_path = str(pt) if pt.exists() else f"{name}.pt"
    if dev != "cpu":
        return pt_path, f"PyTorch ({dev})", dev
    ov = config.MODELS / f"{name}_openvino_model"
    if ov.exists():
        return str(ov), "OpenVINO (CPU)", "cpu"
    return pt_path, "PyTorch (cpu)", "cpu"


class Detector:
    """COCO detector restricted to people, vehicles and bags."""

    def __init__(self) -> None:
        from ultralytics import YOLO

        path, self.backend, self.dev = _resolve(config.DETECTOR_WEIGHTS)
        self.model = YOLO(path, task="detect")
        self.classes = sorted(config.COCO)
        self.name = f"{config.DETECTOR_WEIGHTS} COCO"
        log.info("detector %s via %s", path, self.backend)

    def detect(self, image: np.ndarray):
        """Returns an Ultralytics Boxes object (numpy) for the tracker."""
        with _infer_lock:
            r = self.model.predict(image, imgsz=config.DETECTOR_IMGSZ, conf=0.12, classes=self.classes,
                                   device=None if self.backend.startswith("OpenVINO") else self.dev,
                                   verbose=False)[0]
        return r.boxes.cpu().numpy()


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


_detector: Detector | None = None
_load_lock = threading.Lock()


def get_detector() -> Detector:
    global _detector
    with _load_lock:
        if _detector is None:
            _detector = Detector()
    return _detector
