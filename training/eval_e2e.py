"""End-to-end evaluation of the whole Drishti pipeline on the shared bench set.

    backend\\.venv\\Scripts\\python training\\eval_e2e.py
Writes docs/results/e2e_eval.json.

What is measured, per clip, with the same settings the live system uses:
  accident  incident raised inside [onset - 1 s, annotated end + 10 s] (UCF-Crime annotation)
  crowd     incident raised inside [onset - 1 s, end + 3 s] of each UMN scene
  baggage   any baggage incident on an ABODA clip (ABODA has no onset labels)
  normal    every incident on a normal clip is a false alarm

"Without the filter" counts every candidate group an engine produced (what an unfiltered
system would have alerted on). "With the filter" counts incidents actually raised.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "training" / "bench"))
os.chdir(ROOT / "models")

from app import config  # noqa: E402
from app.offline import run_clip  # noqa: E402
from summarise import onsets  # noqa: E402

BENCH = ROOT / "data" / "bench"
CAP_S = 40.0
ARGS = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
TASKS = set(ARGS.get("tasks", "accident,baggage,crowd,normal").split(","))  # tasks=crowd,normal reruns a subset
OUT = ROOT / "docs" / "results" / f"{ARGS.get('out', 'e2e_eval')}.json"


def main() -> None:
    t0 = time.time()
    rows, totals = [], {"raw": 0, "confirmed": 0, "seconds": 0.0}
    normal = {"raw": 0, "confirmed": 0, "seconds": 0.0}

    def account(r: dict, is_normal: bool = False) -> None:
        totals["raw"] += r["raw_alarms"]
        totals["confirmed"] += len(r["incidents"])
        totals["seconds"] += r["seconds"]
        if is_normal:
            normal["raw"] += r["raw_alarms"]
            normal["confirmed"] += len(r["incidents"])
            normal["seconds"] += r["seconds"]

    ons = onsets()
    acc = {"clips": 0, "detected": 0, "early": 0, "delays": []}
    for clip in sorted((BENCH / "accident").glob("*.mp4")) if "accident" in TASKS else []:
        r = run_clip(clip, "traffic", max_seconds=CAP_S)
        on, end = ons[clip.name]
        hits = [i["ts"] for i in r["incidents"] if i["type"] == "accident" and on - 1 <= i["ts"] <= end + 10]
        early = [i["ts"] for i in r["incidents"] if i["ts"] < on - 1]
        acc["clips"] += 1
        acc["detected"] += bool(hits)
        acc["early"] += len(early)
        if hits:
            acc["delays"].append(round(hits[0] - on, 1))
        rows.append({"task": "accident", "clip": clip.name, "onset_s": round(on, 1), "detected": bool(hits),
                     "delay_s": round(hits[0] - on, 1) if hits else None, "early_alarms": len(early),
                     "raw_alarms": r["raw_alarms"], "suppressed": len(r["suppressed"])})
        account(r)
        print(rows[-1])

    bagr = {"clips": 0, "detected": 0}
    for clip in sorted((BENCH / "baggage").glob("*.mp4")) if "baggage" in TASKS else []:
        r = run_clip(clip, "public")
        hits = [i for i in r["incidents"] if i["type"] == "baggage"]
        other = [i for i in r["incidents"] if i["type"] != "baggage"]
        bagr["clips"] += 1
        bagr["detected"] += bool(hits)
        rows.append({"task": "baggage", "clip": clip.name, "detected": bool(hits),
                     "first_incident_s": round(hits[0]["ts"], 1) if hits else None,
                     "other_incidents": len(other), "raw_alarms": r["raw_alarms"],
                     "suppressed": len(r["suppressed"])})
        account(r)
        print(rows[-1])

    labels = json.loads((BENCH / "crowd" / "umn_labels.json").read_text())
    crowd = {"scenes": 0, "detected": 0, "early": 0, "delays": [], "held_out_detected": 0, "held_out": 0}
    held = {1, 4, 7, 9}
    for si, s in enumerate(labels["scenes"] if "crowd" in TASKS else []):
        r = run_clip(BENCH / "crowd" / "umn_all.avi", "public", mask_rows=24, start_frame=s["start"],
                     end_frame=s["end"], cam_id=f"umn{si}")
        on, end = s["onset"] / 30.0, s["end"] / 30.0
        hits = [i["ts"] for i in r["incidents"] if i["type"] == "crowd" and on - 1 <= i["ts"] <= end + 3]
        early = [i["ts"] for i in r["incidents"] if i["ts"] < on - 1]
        crowd["scenes"] += 1
        crowd["detected"] += bool(hits)
        crowd["early"] += len(early)
        if si in held:
            crowd["held_out"] += 1
            crowd["held_out_detected"] += bool(hits)
        if hits:
            crowd["delays"].append(round(hits[0] - on, 1))
        rows.append({"task": "crowd", "clip": f"UMN scene {si}" + (" (held out)" if si in held else " (in training)"),
                     "abnormal_s": round(end - on, 1), "detected": bool(hits),
                     "delay_s": round(hits[0] - on, 1) if hits else None, "early_alarms": len(early),
                     "raw_alarms": r["raw_alarms"], "suppressed": len(r["suppressed"])})
        account(r)
        print(rows[-1])

    norm_rows = []
    for clip in sorted((BENCH / "normal").glob("*.mp4")) if "normal" in TASKS else []:
        r = run_clip(clip, "mixed", max_seconds=CAP_S)
        norm_rows.append({"task": "normal", "clip": clip.name, "false_alarms_with_filter": len(r["incidents"]),
                          "alarms_without_filter": r["raw_alarms"], "suppressed": len(r["suppressed"]),
                          "incident_types": sorted({i["type"] for i in r["incidents"]}),
                          "proc_fps": r["proc_fps"]})
        account(r, True)
        print(norm_rows[-1])

    def med(v: list[float]):
        return sorted(v)[len(v) // 2] if v else None

    hours = normal["seconds"] / 3600
    res = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "settings": {"gate": config.GATE, "persist_s": config.PERSIST_S, "min_hits": config.MIN_HITS,
                     "bag_unattended_s": config.BAG_UNATTENDED_S, "target_fps": config.TARGET_FPS,
                     "detect_every": config.DETECT_EVERY, "accident_every_s": config.ACCIDENT_EVERY_S,
                     "accident_imgsz": config.ACCIDENT_IMGSZ, "accident_weights": Path(config.ACCIDENT_WEIGHTS).name},
        "accident": {"dataset": "UCF-Crime RoadAccidents, first 8 annotated test videos, first 40 s of each",
                     "clips": acc["clips"], "detected": acc["detected"], "early_alarms": acc["early"],
                     "median_delay_s": med(acc["delays"])},
        "baggage": {"dataset": "ABODA videos 1, 2, 3, 4, 9, 10", **bagr},
        "crowd": {"dataset": "UMN, 11 scenes (4 held out from training)", "scenes": crowd["scenes"],
                  "detected": crowd["detected"], "held_out_scenes": crowd["held_out"],
                  "held_out_detected": crowd["held_out_detected"], "early_alarms": crowd["early"],
                  "median_delay_s": med(crowd["delays"])},
        "normal": {"dataset": "UCF-Crime Testing_Normal videos 006, 015, 018, 024, first 40 s of each",
                   "clips": len(norm_rows), "camera_seconds": round(normal["seconds"], 1),
                   "alarms_without_filter": normal["raw"], "false_alarms_with_filter": normal["confirmed"],
                   "per_camera_hour_without_filter": round(normal["raw"] / hours, 1) if hours else None,
                   "per_camera_hour_with_filter": round(normal["confirmed"] / hours, 1) if hours else None},
        "all_footage": {"camera_seconds": round(totals["seconds"], 1), "alarm_groups_without_filter": totals["raw"],
                        "incidents_with_filter": totals["confirmed"]},
        "rows": rows + norm_rows,
        "runtime_s": round(time.time() - t0),
    }
    # a partial rerun keeps the sections it did not touch from the previous file
    if OUT.exists() and TASKS != {"accident", "baggage", "crowd", "normal"}:
        prev = json.loads(OUT.read_text())
        for t in ("accident", "baggage", "crowd", "normal"):
            if t not in TASKS and t in prev:
                res[t] = prev[t]
                res["rows"] += [r for r in prev["rows"] if r["task"] == t]
        kept = [r for r in res["rows"]]
        res["all_footage"] = {"note": "combined from two runs", **prev.get("all_footage", {})}
        res["rows"] = sorted(kept, key=lambda r: ["accident", "baggage", "crowd", "normal"].index(r["task"]))
    for t in ("accident", "baggage", "crowd", "normal"):
        if t not in TASKS and not OUT.exists():
            res.pop(t, None)
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
