"""Paths and tunables. Everything that changes behaviour lives here or in .env."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


DATA = ROOT / "data"
MODELS = ROOT / "models"
RESULTS = ROOT / "docs" / "results"
MEDIA = DATA / "media"
UPLOADS = DATA / "uploads"
DEMO = DATA / "demo"
DB_PATH = Path(os.environ.get("DRISHTI_DB", DATA / "drishti.db"))
FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
FRONTEND_DIST = ROOT / "frontend" / "dist"

for _p in (MEDIA / "keyframes", MEDIA / "clips", UPLOADS, DEMO, MODELS):
    _p.mkdir(parents=True, exist_ok=True)

DEMO_MODE = _flag("DRISHTI_DEMO")

# ---- ingestion
TARGET_FPS = float(os.environ.get("DRISHTI_TARGET_FPS", 10))
DETECT_EVERY = int(os.environ.get("DRISHTI_DETECT_EVERY", 2))  # run YOLO on every Nth sampled frame
RING_SECONDS = 10.0
STREAM_WIDTH = 640
JPEG_QUALITY = 72

# ---- models
DETECTOR_WEIGHTS = os.environ.get("DRISHTI_DETECTOR", "yolo11n")
DETECTOR_IMGSZ = int(os.environ.get("DRISHTI_IMGSZ", 480))
ACCIDENT_WEIGHTS = os.environ.get("DRISHTI_ACCIDENT_WEIGHTS", str(MODELS / "accident.pt"))
ACCIDENT_EVERY_S = float(os.environ.get("DRISHTI_ACCIDENT_EVERY_S", 1.0))
ACCIDENT_IMGSZ = int(os.environ.get("DRISHTI_ACCIDENT_IMGSZ", 640))
CROWD_MODEL = MODELS / "crowd_tcn.pt"

COCO = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck",
        24: "backpack", 26: "handbag", 28: "suitcase"}
VEHICLES = {"car", "motorcycle", "bus", "truck", "bicycle"}
BAGS = {"backpack", "handbag", "suitcase"}

# ---- engines
BAG_UNATTENDED_S = float(os.environ.get("DRISHTI_BAG_UNATTENDED_S", 10))
BAG_ABANDONED_S = float(os.environ.get("DRISHTI_BAG_ABANDONED_S", 30))
CROWD_LIMIT = int(os.environ.get("DRISHTI_CROWD_LIMIT", 25))

# ---- false-alarm filter: base confidence gate and persistence per incident type
GATE = {"accident": 0.45, "crowd": 0.60, "baggage": 0.18}
PERSIST_S = {"accident": 1.0, "crowd": 2.0, "baggage": 0.0}
MIN_HITS = {"accident": 2, "crowd": 4, "baggage": 1}
GROUP_GAP_S = 6.0
MERGE_WINDOW_S = 30.0
DISMISS_STEP = 0.05
CONFIRM_STEP = 0.02
MAX_ADJ = 0.25

# ---- optional integrations, off unless configured in .env
TELEGRAM_ENABLED = _flag("TELEGRAM_ENABLED")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
VISION_VERIFY_ENABLED = _flag("VISION_VERIFY_ENABLED")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "claude-opus-5-5")
