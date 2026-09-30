"""Frame-level labels for the UMN crowd dataset.

The single UMN video burns a red "Abnormal Crowd Activity" caption into the top-left
corner of every abnormal frame. We read that caption to get per-frame labels and scene
boundaries, then hide the top strip before any model sees a frame (see `mask_caption`).

Output: data/bench/crowd/umn_labels.json
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "data" / "bench" / "crowd" / "umn_all.avi"
CAPTION_ROWS = 24


def mask_caption(frame: np.ndarray) -> np.ndarray:
    frame[:CAPTION_ROWS] = 0
    return frame


def main() -> None:
    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS)
    red_counts = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        strip = f[10:23, :180].astype(int)
        b, g, r = strip[..., 0], strip[..., 1], strip[..., 2]
        red_counts.append(int(((r - g > 60) & (r - b > 60)).sum()))
    cap.release()
    raw = np.array(red_counts) > 150
    # close gaps shorter than 5 frames so codec noise does not split a caption
    labels = raw.copy()
    k = 5
    for i in range(len(raw)):
        lo, hi = max(0, i - k), min(len(raw), i + k + 1)
        labels[i] = raw[lo:hi].sum() > k
    scenes, start, onset = [], 0, None
    for i in range(1, len(labels)):
        if labels[i] and not labels[i - 1] and onset is None:
            onset = i
        if not labels[i] and labels[i - 1]:
            scenes.append({"start": start, "onset": onset, "end": i - 1})
            start, onset = i, None
    if onset is not None:
        scenes.append({"start": start, "onset": onset, "end": len(labels) - 1})
    out = {"video": "umn_all.avi", "fps": fps, "frames": len(labels),
           "abnormal_frames": int(labels.sum()), "scenes": scenes,
           "labels": [int(x) for x in labels]}
    (VIDEO.parent / "umn_labels.json").write_text(json.dumps(out))
    print(f"{len(labels)} frames, {int(labels.sum())} abnormal, {len(scenes)} scenes")
    for s in scenes:
        print(s)


if __name__ == "__main__":
    main()
