"""The extra detectors that run next to the COCO detector on every camera.

Each model is run at its own cadence (seconds between calls per camera) because the big
ones cannot run on every frame. Live, one scheduler thread takes turns across cameras and
models, so a slow model never stalls the video; offline (evaluation, demo cache) they are
called directly at the same cadence.

| name      | model (licence)                                              | output                    |
|-----------|--------------------------------------------------------------|---------------------------|
| accident  | Enos-123 YOLO11x accident detector (MIT)                     | boxes: accident, vehicle  |
| fire      | rabahdev/fire-smoke-yolov8n, D-Fire dataset (AGPL-3.0)       | boxes: smoke, fire        |
| weapon    | weapon_detector.pt from saadkhan2003/CCTV_Video_Anomaly_Detection (Apache-2.0) | boxes: pistol, knife |
| fall      | melihuzunoglu/human-fall-detection (AGPL-3.0)                | boxes: fallen, sitting, standing |
| violence  | jaranohaal/vit-base-violence-detection, timm ViT-B/16 (Apache-2.0) | P(violent scene)     |
| scene     | google/siglip-base-patch16-224, zero-shot (Apache-2.0)       | score per scene prompt    |
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import numpy as np

from . import config

log = logging.getLogger("drishti.aux")
_load_lock = threading.Lock()


def device() -> str:
    """cuda on an NVIDIA machine, mps on Apple silicon, else cpu."""
    forced = os.environ.get("DRISHTI_DEVICE")
    if forced:
        return forced
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# Scene prompts for the zero-shot model. Each group is scored as its best prompt minus the
# best "normal" prompt, so a scene only counts when it looks more like the incident than
# like an ordinary scene of the same place.
SCENE_GROUPS: dict[str, list[str]] = {
    "fire": ["a CCTV image of a fire", "a CCTV image of flames", "a CCTV image of a burning car"],
    "smoke": ["a CCTV image of thick smoke", "a CCTV image of a room filling with smoke"],
    "explosion": ["a CCTV image of an explosion", "a CCTV image of a blast with debris flying"],
    "flood": ["a CCTV image of a flooded street", "a CCTV image of water flooding a building"],
    "fight": ["a CCTV image of people fighting", "a CCTV image of a person punching another person",
              "a CCTV image of a violent assault"],
    "robbery": ["a CCTV image of a robbery at gunpoint", "a CCTV image of a thief snatching a bag"],
    "vandalism": ["a CCTV image of someone smashing a window", "a CCTV image of vandalism"],
    "crash": ["a CCTV image of a car crash", "a CCTV image of a road accident"],
    "collapse": ["a CCTV image of a person lying unconscious on the ground",
                 "a CCTV image of a person who has fallen down"],
    "stampede": ["a CCTV image of a crowd stampede", "a CCTV image of people running away in panic"],
    "animal": ["a CCTV image of an animal on the road", "a CCTV image of cattle blocking traffic"],
}
NORMAL_PROMPTS = ["a CCTV image of an ordinary street", "a CCTV image of people walking normally",
                  "a CCTV image of an empty room", "a CCTV image of normal traffic",
                  "a CCTV image of a shop with customers"]


class AuxModel:
    name = ""
    every_s = 1.0

    def __init__(self) -> None:
        self.available = False
        self.backend = ""

    def run(self, image: np.ndarray) -> dict:
        raise NotImplementedError


class YoloAux(AuxModel):
    def __init__(self, name: str, path: Path, every_s: float, imgsz: int = 640, conf: float = 0.25) -> None:
        super().__init__()
        self.name, self.every_s, self.imgsz, self.conf = name, every_s, imgsz, conf
        if not path.exists():
            log.warning("%s: no weights at %s, engine uses its fallback", name, path)
            return
        from ultralytics import YOLO

        self.model = YOLO(str(path), task="detect")
        self.names = dict(self.model.names)
        self.dev = device()
        self.backend = f"PyTorch ({self.dev})"
        self.available = True

    def run(self, image: np.ndarray) -> dict:
        with config.INFER_LOCK:
            r = self.model.predict(image, imgsz=self.imgsz, conf=self.conf, device=self.dev, verbose=False)[0]
        return {"dets": [{"cls": self.names[int(c)], "conf": round(float(p), 3),
                          "box": [round(float(v), 1) for v in b]}
                         for b, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist())]}


class ViolenceAux(AuxModel):
    """ViT-B/16 image classifier. The published checkpoint is in timm format (loading it
    with transformers silently gives a random classifier head), so it is loaded with timm."""
    name = "violence"

    def __init__(self, every_s: float) -> None:
        super().__init__()
        self.every_s = every_s
        path = config.MODELS / "violence_vit" / "model.safetensors"
        if not path.exists():
            log.warning("violence: no weights at %s", path)
            return
        import timm
        import torch
        from safetensors.torch import load_file

        self.torch = torch
        self.dev = device()
        self.model = timm.create_model("vit_base_patch16_224", pretrained=False, num_classes=2)
        self.model.load_state_dict(load_file(str(path)))
        self.model.eval().to(self.dev)
        self.violent_index = int(os.environ.get("DRISHTI_VIOLENCE_INDEX", config.VIOLENCE_INDEX))
        self.backend = f"PyTorch ({self.dev})"
        self.available = True

    def run(self, image: np.ndarray) -> dict:
        import cv2

        rgb = cv2.cvtColor(cv2.resize(image, (224, 224), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        x = (rgb.astype(np.float32) / 255.0 - 0.5) / 0.5
        t = self.torch.from_numpy(x.transpose(2, 0, 1)[None]).to(self.dev)
        with config.INFER_LOCK, self.torch.no_grad():
            p = self.torch.softmax(self.model(t), -1)[0].float().cpu().numpy()
        return {"p": round(float(p[self.violent_index]), 4)}


class SceneAux(AuxModel):
    """SigLIP zero-shot scene scores for the long tail: flood, explosion, vandalism, animals,
    and a second opinion on fire, fights, crashes and collapses."""
    name = "scene"

    def __init__(self, every_s: float) -> None:
        super().__init__()
        self.every_s = every_s
        path = config.MODELS / "siglip"
        if not (path / "model.safetensors").exists():
            log.warning("scene: no SigLIP weights at %s", path)
            return
        import torch
        from transformers import AutoModel, AutoProcessor

        self.torch = torch
        self.dev = device()
        self.proc = AutoProcessor.from_pretrained(str(path))
        dtype = torch.float16 if self.dev in {"cuda", "mps"} else torch.float32
        self.model = AutoModel.from_pretrained(str(path), torch_dtype=dtype).eval().to(self.dev)
        self.dtype = dtype
        self.prompts = [p for g in SCENE_GROUPS.values() for p in g] + NORMAL_PROMPTS
        with torch.no_grad():  # text side is fixed: embed the prompts once
            tok = self.proc(text=self.prompts, padding="max_length", return_tensors="pt").to(self.dev)
            te = self.model.get_text_features(**tok)
            self.text = te / te.norm(dim=-1, keepdim=True)
        self.backend = f"PyTorch ({self.dev})"
        # supervised accident classifier trained on these same image features
        # (training/train_accident_clf.py); optional
        self.acc_w = self.acc_b = None
        clf = config.MODELS / "accident_clf.json"
        if clf.exists():
            import json

            d = json.loads(clf.read_text())
            self.acc_w, self.acc_b, self.acc_thr = np.array(d["coef"], dtype=np.float32), d["intercept"], d["threshold"]
        self.available = True

    def run(self, image: np.ndarray) -> dict:
        import cv2

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        with config.INFER_LOCK, self.torch.no_grad():
            px = self.proc(images=rgb, return_tensors="pt")["pixel_values"].to(self.dev, self.dtype)
            ie = self.model.get_image_features(pixel_values=px)
            ie = ie / ie.norm(dim=-1, keepdim=True)
            logits = (ie @ self.text.T)[0] * self.model.logit_scale.exp() + self.model.logit_bias
            prob = self.torch.sigmoid(logits).float().cpu().numpy()
            emb = ie[0].float().cpu().numpy()
        scores = dict(zip(self.prompts, prob.tolist()))
        normal = max(scores[p] for p in NORMAL_PROMPTS)
        out = {"groups": {g: round(max(scores[p] for p in ps), 5) for g, ps in SCENE_GROUPS.items()},
               "normal": round(normal, 5)}
        if self.acc_w is not None:
            z = float(emb @ self.acc_w + self.acc_b)
            out["accident_p"] = round(1.0 / (1.0 + np.exp(-max(-30.0, min(30.0, z)))), 4)
            out["accident_thr"] = self.acc_thr
        return out


_models: dict[str, AuxModel] | None = None


def get_models() -> dict[str, AuxModel]:
    """All auxiliary models, loaded once. Missing weights leave a model unavailable."""
    global _models
    with _load_lock:
        if _models is None:
            m: dict[str, AuxModel] = {}
            acc_path = Path(config.ACCIDENT_WEIGHTS)
            m["accident"] = YoloAux("accident", acc_path, config.EVERY_S["accident"], imgsz=config.ACCIDENT_IMGSZ)
            m["fire"] = YoloAux("fire", config.MODELS / "fire_smoke.pt", config.EVERY_S["fire"], conf=0.2)
            m["weapon"] = YoloAux("weapon", config.MODELS / "weapon.pt", config.EVERY_S["weapon"], conf=0.3)
            m["fall"] = YoloAux("fall", config.MODELS / "fall.pt", config.EVERY_S["fall"], conf=0.3)
            m["violence"] = ViolenceAux(config.EVERY_S["violence"])
            m["scene"] = SceneAux(config.EVERY_S["scene"])
            _models = {k: v for k, v in m.items() if k in config.ENABLED_AUX}
            log.info("aux models: %s", {k: (v.available, v.backend) for k, v in _models.items()})
    return _models


class AuxScheduler:
    """Live mode: one thread runs the auxiliary models for every camera, oldest request
    first, and keeps the latest result per (camera, model)."""

    def __init__(self) -> None:
        self.models = get_models()
        self.frames: dict[str, tuple[np.ndarray, float]] = {}
        self.last_run: dict[tuple[str, str], float] = {}
        self.results: dict[tuple[str, str], tuple[dict, float]] = {}
        self.ms: dict[str, float] = {}
        self.cv = threading.Condition()
        threading.Thread(target=self._loop, daemon=True, name="aux-models").start()

    def offer(self, cam: str, image: np.ndarray, ts: float) -> None:
        with self.cv:
            self.frames[cam] = (image, ts)
            self.cv.notify()

    def take(self, cam: str) -> dict[str, dict]:
        """Results that arrived since the last call, by model name."""
        out = {}
        for (c, name), (res, _) in list(self.results.items()):
            if c == cam:
                out[name] = self.results.pop((c, name))[0]
        return out

    def _next(self) -> tuple[str, str] | None:
        now, best, best_wait = time.time(), None, 0.0
        for cam in self.frames:
            for name, m in self.models.items():
                if not m.available:
                    continue
                wait = now - self.last_run.get((cam, name), 0.0) - m.every_s
                if wait >= 0 and (best is None or wait > best_wait):
                    best, best_wait = (cam, name), wait
        return best

    def _loop(self) -> None:
        while True:
            with self.cv:
                job = self._next()
                if job is None:
                    self.cv.wait(timeout=0.05)
                    continue
                cam, name = job
                image, ts = self.frames[cam]
                self.last_run[job] = time.time()
            t0 = time.perf_counter()
            try:
                res = self.models[name].run(image)
            except Exception:  # noqa: BLE001
                log.exception("aux model %s failed", name)
                continue
            self.ms[name] = round((time.perf_counter() - t0) * 1000)
            self.results[job] = (res, ts)


_scheduler: AuxScheduler | None = None
_sched_lock = threading.Lock()


def get_scheduler() -> AuxScheduler:
    global _scheduler
    with _sched_lock:
        if _scheduler is None:
            _scheduler = AuxScheduler()
    return _scheduler
