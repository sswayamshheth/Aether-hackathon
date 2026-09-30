"""Download the pinned COCO detector and export it (and the accident model, if present)
to OpenVINO, then time PyTorch vs OpenVINO on this machine.

    backend\\.venv\\Scripts\\python training\\export_models.py
Writes docs/results/inference_speed.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
os.chdir(MODELS)
sys.path.insert(0, str(ROOT / "backend"))

from ultralytics import YOLO  # noqa: E402


def export(name: str, imgsz: int) -> Path:
    out = MODELS / f"{name}_openvino_model"
    if not out.exists():
        made = YOLO(f"{name}.pt").export(format="openvino", imgsz=imgsz, dynamic=True, half=False)
        if Path(made).resolve() != out.resolve():
            shutil.move(made, out)
    return out


def bench(path: str, imgsz: int, n: int = 40) -> float:
    model = YOLO(path, task="detect")
    img = (np.random.rand(360, 480, 3) * 255).astype("uint8")
    for _ in range(3):
        model.predict(img, imgsz=imgsz, verbose=False)
    t0 = time.perf_counter()
    for _ in range(n):
        model.predict(img, imgsz=imgsz, verbose=False)
    return round(n / (time.perf_counter() - t0), 1)


def main() -> None:
    res = {"machine": "Intel i5-1230U, CPU only", "input": "480x360 frame", "models": {}}
    ov = export("yolo11n", 480)
    res["models"]["yolo11n COCO"] = {"imgsz": 480, "pytorch_fps": bench("yolo11n.pt", 480),
                                     "openvino_fps": bench(str(ov), 480)}
    acc = MODELS / "accident.pt"
    if acc.exists():
        ov = export("accident", 640)
        n = 12
        res["models"]["accident detector"] = {"imgsz": 640, "pytorch_fps": bench(str(acc), 640, n),
                                              "openvino_fps": bench(str(ov), 640, n)}
    (ROOT / "docs" / "results" / "inference_speed.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
