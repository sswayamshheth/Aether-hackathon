"""Turn raw bench series (docs/results/bench_*.json) into per-clip verdicts.

Accident weights are scored with one fixed alarm rule for every model:
  alarm = accident-class confidence >= THR on 2 consecutive samples (samples are 0.5 s apart)
  detected      = an alarm inside [onset - 1 s, annotated end + 3 s]
  delay         = first such alarm minus annotated onset
  early alarm   = an alarm more than 1 s before onset (counted as a false alarm)
  false alarm   = any alarm on a normal clip
Onset and end frames come from UCF-Crime's Temporal_Anomaly_Annotation file (30 fps).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "docs" / "results"
ANN = ROOT / "data" / "bench" / "_raw" / "ucf_temporal_annotations.txt"
NEG = ("non", "no_", "no-", "no ", "vehicle", "car", "normal")


def positive(name: str) -> bool:
    n = name.lower()
    return not any(n.startswith(w) for w in NEG)


def onsets() -> dict[str, tuple[float, float]]:
    out = {}
    for line in ANN.read_text().splitlines():
        p = line.split()
        if len(p) >= 4 and p[1] == "RoadAccidents":
            out[p[0]] = (int(p[2]) / 30.0, int(p[3]) / 30.0)
    return out


def alarms(series: list[dict], thr: float, classes: set[str] | None) -> list[float]:
    out, run = [], 0
    for s in series:
        c = max((v for k, v in s["conf"].items() if positive(k) and (classes is None or k in classes)),
                default=0.0)
        run = run + 1 if c >= thr else 0
        if run == 2:
            out.append(s["t"])
    return out


def accident(name: str, thr: float = 0.5, classes: set[str] | None = None) -> dict:
    raw = json.loads((RES / f"bench_{name}.json").read_text())
    ons = onsets()
    rows, det, early, fa_clips, fa_total, delays = [], 0, 0, 0, 0, []
    for clip, series in raw["clips"].items():
        group, fname = clip.split("/")
        al = alarms(series, thr, classes)
        if group == "accident":
            on, end = ons[fname]
            hit = [t for t in al if on - 1 <= t <= end + 3]
            pre = [t for t in al if t < on - 1]
            det += bool(hit)
            early += len(pre)
            if hit:
                delays.append(hit[0] - on)
            rows.append({"clip": fname, "onset_s": round(on, 1), "detected": bool(hit),
                         "delay_s": round(hit[0] - on, 1) if hit else None, "early_alarms": len(pre)})
        else:
            fa_clips += bool(al)
            fa_total += len(al)
            rows.append({"clip": fname, "normal": True, "false_alarms": len(al)})
    n_acc = sum(1 for r in rows if "normal" not in r)
    n_norm = len(rows) - n_acc
    return {"model": name, "threshold": thr, "classes_used": sorted(classes) if classes else "all positive",
            "all_classes": raw["classes"], "accident_clips": n_acc, "detected": det,
            "median_delay_s": round(sorted(delays)[len(delays) // 2], 1) if delays else None,
            "early_alarms": early, "normal_clips": n_norm, "normal_clips_with_false_alarm": fa_clips,
            "false_alarms_on_normal": fa_total, "infer_fps": raw["infer_fps"], "rss_mb": raw["rss_mb"],
            "rows": rows}


if __name__ == "__main__":
    for thr in (0.3, 0.5, 0.7):
        r = accident(sys.argv[1], thr, set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None)
        print(json.dumps({k: v for k, v in r.items() if k != "rows"}))
        if thr == 0.5:
            for row in r["rows"]:
                print("   ", row)
