"""Download every model weight the project uses, at pinned revisions, into models/.
Skips anything already present, so it is safe to run on a folder copied from another machine.

    backend/.venv/bin/python training/get_models.py        (macOS / Linux)
    backend\\.venv\\Scripts\\python training\\get_models.py  (Windows)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / "models"
M.mkdir(exist_ok=True)
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "hf"))
os.environ.pop("HF_HUB_OFFLINE", None)

from huggingface_hub import hf_hub_download, snapshot_download  # noqa: E402

FILES = {  # target: (repo, file, revision, licence)
    "accident.pt": ("Enos-123/traffic-accident-detection-yolo11x", "weights/epoch61.pt", "cdc556d278", "MIT"),
    "fire_smoke.pt": ("rabahdev/fire-smoke-yolov8n", "best.pt", "13017fe8af", "AGPL-3.0"),
    "fall.pt": ("melihuzunoglu/human-fall-detection", "best.pt", "97261b0363", "AGPL-3.0"),
}
FOLDERS = {
    "violence_vit": ("jaranohaal/vit-base-violence-detection", "31931091df", ["*.json", "model.safetensors"], "Apache-2.0"),
    "siglip": ("google/siglip-base-patch16-224", "7fd15f0689", ["*.json", "model.safetensors", "*.model"], "Apache-2.0"),
}


def main() -> None:
    for name, (repo, file, rev, lic) in FILES.items():
        if not (M / name).exists():
            shutil.copy(hf_hub_download(repo, file, revision=rev), M / name)
        print(f"ok  {name:16} {repo} ({lic})")
    for name, (repo, rev, patterns, lic) in FOLDERS.items():
        if not (M / name / "model.safetensors").exists():
            snapshot_download(repo, revision=rev, local_dir=str(M / name), allow_patterns=patterns)
        print(f"ok  {name:16} {repo} ({lic})")
    weapon = M / "weapon.pt"
    src = ROOT / "_reference" / "saadkhan-anomaly" / "models" / "weapon_detector.pt"
    if not weapon.exists() and src.exists():
        shutil.copy(src, weapon)
    print(f"{'ok ' if weapon.exists() else 'MISSING'} weapon.pt        from github.com/saadkhan2003/CCTV_Video_Anomaly_Detection "
          "(Apache-2.0), file models/weapon_detector.pt at commit 4ab4eb0349")
    if not (M / "yolo11n.pt").exists():
        from ultralytics import YOLO

        os.chdir(M)
        YOLO("yolo11n.pt")
    print("ok  yolo11n.pt        Ultralytics COCO (AGPL-3.0)")
    crowd = M / "crowd_tcn.pt"
    print(f"{'ok ' if crowd.exists() else 'MISSING'} crowd_tcn.pt     trained by training/train_crowd.py (copy it from the build machine)")
    ver = M / "verifiers.json"
    print(f"{'ok ' if ver.exists() else 'MISSING'} verifiers.json   trained by training/train_verifiers.py")


if __name__ == "__main__":
    main()
