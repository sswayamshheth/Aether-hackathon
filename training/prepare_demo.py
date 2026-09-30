"""Build the four demo clips and the demo-mode detection cache.

    backend\\.venv\\Scripts\\python training\\prepare_demo.py

Clips (data/demo/clips):
  cam1  UCF-Crime road accident clip (traffic)
  cam2  the same clip mirrored and cropped: a stand-in for a second camera on the junction
  cam3  ABODA video (abandoned bag)
  cam4  UMN scene 4 (crowd dispersal). Scene 4 was held out when the crowd model was trained.

Cache (data/demo/cache/<cam>.json): the tracks and accident detections our pipeline
produced for every processed frame, so demo mode can replay them without running models.
Also writes docs/results/demo_run.json with what the pipeline raised on each clip.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "models")

from app import config  # noqa: E402
from app.offline import run_clip  # noqa: E402

BENCH = ROOT / "data" / "bench"
CLIPS = config.DEMO / "clips"
CACHE = config.DEMO / "cache"
ACCIDENT_CLIP = os.environ.get("DEMO_ACCIDENT_CLIP", "RoadAccidents012_x264.mp4")
BAGGAGE_CLIP = os.environ.get("DEMO_BAGGAGE_CLIP", "aboda_video1.mp4")
UMN_SCENE = 4


def ff(*args: str) -> None:
    subprocess.run([str(config.FFMPEG), "-v", "error", "-y", *args], check=True)


def build_clips() -> None:
    CLIPS.mkdir(parents=True, exist_ok=True)
    enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    acc = str(BENCH / "accident" / ACCIDENT_CLIP)
    ff("-i", acc, "-t", "40", *enc, str(CLIPS / "cam1.mp4"))
    ff("-i", acc, "-t", "40", "-vf", "hflip,crop=iw*0.86:ih*0.86:iw*0.07:ih*0.10,scale=320:240", *enc,
       str(CLIPS / "cam2.mp4"))
    ff("-i", str(BENCH / "baggage" / BAGGAGE_CLIP), *enc, str(CLIPS / "cam3.mp4"))
    labels = json.loads((BENCH / "crowd" / "umn_labels.json").read_text())
    s = labels["scenes"][UMN_SCENE]
    fps = labels["fps"]
    # the dataset's burnt-in caption is covered, exactly as it was for training
    ff("-ss", f"{s['start'] / fps:.3f}", "-i", str(BENCH / "crowd" / "umn_all.avi"),
       "-t", f"{(s['end'] - s['start']) / fps:.3f}", "-vf", "drawbox=x=0:y=0:w=iw:h=24:color=black:t=fill",
       *enc, str(CLIPS / "cam4.mp4"))


def build_cache() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    seed = json.loads((ROOT / "scripts" / "cameras.json").read_text())["cameras"]
    report = {}
    for c in seed:
        r = run_clip(ROOT / c["clip"], c["profile"], cam_id=c["id"], record=True)
        (CACHE / f"{c['id']}.json").write_text(json.dumps(r["cache"]))
        report[c["id"]] = {"clip": c["clip"], "profile": c["profile"], "seconds": r["seconds"],
                           "frames_processed": r["frames"], "offline_fps": r["proc_fps"],
                           "incidents": [{"type": i["type"], "subtype": i["subtype"], "at_s": round(i["ts"], 1)}
                                         for i in r["incidents"]],
                           "suppressed": len(r["suppressed"]), "raw_alarms": r["raw_alarms"]}
        print(c["id"], report[c["id"]])
    (ROOT / "docs" / "results" / "demo_run.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    build_clips()
    build_cache()
