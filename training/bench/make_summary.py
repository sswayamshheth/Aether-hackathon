"""Build docs/results/summary.json (read by the dashboard's Models page) and BENCH.md from
the raw result files. Every number in both comes from a JSON file written by a script in
this repo; this file only formats them.

    backend\\.venv\\Scripts\\python training\\bench\\make_summary.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "docs" / "results"
sys.path.insert(0, str(Path(__file__).parent))
import summarise  # noqa: E402

MACHINE = "Intel i5-1230U, 16 GB RAM, no GPU, Windows 11"


def load(name: str):
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def col(key: str, label: str, right: bool = False) -> dict:
    return {"key": key, "label": label, **({"align": "right"} if right else {})}


def accident_section() -> dict | None:
    models = [
        ("srniloy_yolo11n", "srniloy/accident-detection, YOLO11n", "none (no licence file)", "2 fps"),
        ("enos_yolo11x", "Enos-123 traffic-accident-detection, YOLO11x @640", "MIT (Hugging Face card)", "1 fps"),
        ("enos_yolo11x_320", "Enos-123 traffic-accident-detection, YOLO11x @320", "MIT (Hugging Face card)", "1 fps"),
    ]
    rows = []
    for key, label, lic, rate in models:
        if not load(f"bench_{key}"):
            continue
        r = summarise.accident(key, 0.5)
        rows.append({"model": label, "licence": lic, "sampled": rate,
                     "detected": f"{r['detected']} / {r['accident_clips']}",
                     "delay": r["median_delay_s"], "early": r["early_alarms"],
                     "fa": f"{r['false_alarms_on_normal']} on {r['normal_clips_with_false_alarm']} of {r['normal_clips']} clips",
                     "fps": r["infer_fps"], "ram": r["rss_mb"]})
    if not rows:
        return None
    return {
        "title": "Accident detectors, per-frame weights only",
        "meta": "UCF-Crime RoadAccidents: 8 clips, plus 4 normal clips",
        "columns": [col("model", "Weights"), col("licence", "Licence"), col("sampled", "Sampled at"),
                    col("detected", "Detected", True), col("delay", "Median delay (s)", True),
                    col("early", "Alarms before onset", True), col("fa", "False alarms on normal clips"),
                    col("fps", "FPS", True), col("ram", "RAM (MB)", True)],
        "rows": rows,
        "note": "One alarm rule for every model: accident-class confidence of 0.5 or more on 2 consecutive samples. "
                "Detected means an alarm started between 1 s before the annotated onset and 3 s after the annotated end. "
                "An alarm that started earlier counts as an alarm before onset, not as a detection. "
                "First 40 s of each clip. FPS was measured while other jobs were running on the machine.",
    }


def neyvur_section() -> dict | None:
    r = load("bench_neyvur")
    if not r:
        return None
    ons = summarise.onsets()
    rows = []
    for clip, v in r["clips"].items():
        name = clip.split("/")[1]
        ev = v.get("events") or []  # each event is [start_s, end_s, type]
        acc = [e for e in ev if e[2] == "accident"]
        other = sorted({e[2] for e in ev if e[2] != "accident"})
        rows.append({"clip": name, "onset": round(ons[name][0], 1) if name in ons else None,
                     "accident_at": ", ".join(f"{e[0]:.1f} s" for e in acc) or "none",
                     "other": ", ".join(other) or "none", "fps": v.get("fps")})
    return {"title": "Trajectory rules (neyvur/traffic-video-analysis)",
            "meta": f"4 accident clips + 1 normal road clip, every frame, {r['rss_mb']} MB",
            "columns": [col("clip", "Clip"), col("onset", "Annotated onset (s)", True),
                        col("accident_at", "Accident events at"), col("other", "Other event types raised"),
                        col("fps", "FPS", True)],
            "rows": rows,
            "note": "The repo's own YOLOv8n COCO weights, tracker and rules, run unchanged with default settings and no zone "
                    "file. Onset is n/a for the normal clip, where any event is a false alarm."}


def bag_section() -> dict | None:
    r = load("bench_bag_detectors")
    if not r:
        return None
    lic = {"theromanfour_korzo_yolov8s": ("TheRomanFour korzo_model.pt (custom YOLOv8s: luggage, people)", "none (no licence file)"),
           "coco_yolo11n": ("Ultralytics YOLO11n, COCO bag classes", "AGPL-3.0"),
           "coco_yolo11s": ("Ultralytics YOLO11s, COCO bag classes", "AGPL-3.0")}
    rows = []
    for k, v in r["models"].items():
        hit = sum(c["frames_with_bag"] for c in v["clips"].values())
        tot = sum(c["frames"] for c in v["clips"].values())
        per = ", ".join(f"{n.replace('aboda_video', 'v').replace('.mp4', '')}: {c['frames_with_bag']}/{c['frames']}"
                        for n, c in v["clips"].items())
        rows.append({"model": lic[k][0], "licence": lic[k][1], "frames": f"{hit} / {tot}",
                     "share": f"{100 * hit / tot:.0f}%", "per_clip": per, "fps": v["infer_fps"], "ram": v["rss_mb"]})
    return {"title": "Bag detectors", "meta": "ABODA videos 1, 2, 3, 4, 9, 10 sampled at 2 fps",
            "columns": [col("model", "Weights"), col("licence", "Licence"), col("frames", "Frames with a bag box", True),
                        col("share", "Share", True), col("per_clip", "Per clip"), col("fps", "FPS", True),
                        col("ram", "RAM (MB)", True)],
            "rows": rows,
            "note": "ABODA has no box labels, so this is the share of sampled frames with at least one bag-class box at "
                    "confidence 0.25 or more. It shows how often a detector sees a bag at all; it cannot show wrong boxes."}


def baria_sections() -> list[dict]:
    out = []
    b = load("bench_baria_baggage")
    if b:
        rows = []
        for clip, v in b["clips"].items():
            grp, name = clip.split("/")
            rows.append({"clip": name, "kind": "abandoned bag" if grp == "baggage" else "normal",
                         "events": len(v["events"]),
                         "first": v["events"][0]["t"] if v["events"] else None,
                         "bag": f"{v['frames_with_bag']} / {v['frames']}"})
        det = sum(1 for r in rows if r["kind"] != "normal" and r["events"])
        fa = sum(r["events"] for r in rows if r["kind"] == "normal")
        out.append({"title": "Abandoned-object logic (BariaHarshh/CCTV-Surveillance-System)",
                    "meta": f"flagged {det} of 6 ABODA clips, {fa} events on 4 normal clips, {b['pipeline_fps']} fps, {b['rss_mb']} MB",
                    "columns": [col("clip", "Clip"), col("kind", "Kind"), col("events", "Events", True),
                                col("first", "First event (s)", True), col("bag", "Frames with a tracked bag", True)],
                    "rows": rows,
                    "note": "The repo's AbandonedObjectProcessor with default settings, fed by YOLOv8n + ByteTrack as the repo does. "
                            "Its logic is sound; it rarely fires because the COCO detector rarely sees the bag."})
    c = load("bench_baria_crowd")
    if c:
        s = c["series"]
        abn = [x for x in s if x["gt"]]
        nor = [x for x in s if not x["gt"]]
        out.append({"title": "Crowd rule (BariaHarshh/CCTV-Surveillance-System)", "meta": "UMN, all 11 scenes, 5 fps",
                    "columns": [col("rule", "Rule"), col("abn", "Abnormal frames flagged", True),
                                col("nor", "Normal frames flagged", True), col("ram", "RAM (MB)", True)],
                    "rows": [{"rule": c["rule"], "abn": f"{sum(x['alarm'] for x in abn)} / {len(abn)}",
                              "nor": f"{sum(x['alarm'] for x in nor)} / {len(nor)}", "ram": c["rss_mb"]}],
                    "note": "A head-count threshold measures how full a scene is, not whether people are fleeing. "
                            "On UMN it flags calm crowds and misses every dispersal, which is why we trained a temporal model."})
    return out


def saadkhan_section() -> dict | None:
    r = load("bench_saadkhan")
    if not r:
        return None
    flag_keys = sorted({k for row in r["umn"] for k, v in row.items() if isinstance(v, bool)})
    rows = []
    abn = [x for x in r["umn"] if x["gt"]]
    nor = [x for x in r["umn"] if not x["gt"]]
    for k in flag_keys:
        rows.append({"flag": k, "abn": f"{sum(bool(x.get(k)) for x in abn)} / {len(abn)}",
                     "nor": f"{sum(bool(x.get(k)) for x in nor)} / {len(nor)}",
                     "normal_clips": sum(bool(x.get(k)) for rows_ in r["normal"].values() for x in rows_)})
    types = sorted({t for row in r["umn"] for t in row.get("anomaly_types", [])}
                   | {t for rows_ in r["normal"].values() for x in rows_ for t in x.get("anomaly_types", [])})
    for t in types:
        rows.append({"flag": t, "abn": f"{sum(t in x.get('anomaly_types', []) for x in abn)} / {len(abn)}",
                     "nor": f"{sum(t in x.get('anomaly_types', []) for x in nor)} / {len(nor)}",
                     "normal_clips": sum(t in x.get("anomaly_types", []) for rows_ in r["normal"].values() for x in rows_)})
    return {"title": "Anomaly rules (saadkhan2003/CCTV_Video_Anomaly_Detection)",
            "meta": f"UMN at 5 fps, {r['pipeline_fps']} fps, {r['rss_mb']} MB",
            "columns": [col("flag", "Flag raised by the repo"), col("abn", "Abnormal frames", True),
                        col("nor", "Normal frames", True), col("normal_clips", "Frames on 4 normal clips", True)],
            "rows": rows,
            "note": "YOLO11s through OpenVINO with the repo's default thresholds (a crowd is 5 or more people). It flags nearly "
                    "every frame, calm or not, so it cannot separate a dispersal from a normal crowd. Needed one fix to run: "
                    "imageio is imported but missing from its requirements.txt."}


def ours_sections() -> list[dict]:
    out = []
    c = load("crowd_model")
    if c:
        out.append({"title": "Our crowd model (temporal CNN)", "meta": c["dataset"],
                    "columns": [col("metric", "Metric"), col("value", "Value", True), col("detail", "Detail")],
                    "rows": [
                        {"metric": "Frame-level AUC, held-out scenes", "value": c["frame_auc_test"],
                         "detail": f"scenes {c['test_scenes']}, {c['test_windows']} windows, {c['test_abnormal_windows']} abnormal"},
                        {"metric": "Frame-level AUC, training scenes", "value": c["frame_auc_train"],
                         "detail": f"scenes {c['train_scenes']}, {c['train_windows']} windows"},
                        {"metric": "Precision at 0.5, held-out", "value": c["precision_at_0.5"], "detail": ""},
                        {"metric": "Recall at 0.5, held-out", "value": c["recall_at_0.5"], "detail": ""},
                        {"metric": "Baseline AUC: flow magnitude alone", "value": c["baseline_auc_test_flow_mean_only"], "detail": "same held-out windows"},
                        {"metric": "Baseline AUC: fastest person alone", "value": c["baseline_auc_test_speed_max_only"], "detail": "same held-out windows"},
                    ],
                    "note": f"{c['model']}. Split {c['split']}. {c['note']}"})
    s = load("inference_speed")
    if s:
        out.append({"title": "Inference speed on this machine", "meta": s["input"],
                    "columns": [col("model", "Model"), col("imgsz", "Input size", True),
                                col("pytorch_fps", "PyTorch FPS", True), col("openvino_fps", "OpenVINO FPS", True)],
                    "rows": [{"model": k, **v} for k, v in s["models"].items()],
                    "note": "Single-image inference, measured while other jobs were running. "
                            "The accident model runs in PyTorch on its own thread: its OpenVINO export was slower here."})
    e = load("e2e_eval")
    if e:
        a, b, cr, n = e["accident"], e["baggage"], e["crowd"], e["normal"]
        raw_all = sum(r.get("raw_alarms", r.get("alarms_without_filter", 0)) for r in e["rows"])
        sup_all = sum(r.get("suppressed", 0) for r in e["rows"])
        out.append({"title": "End to end: whole pipeline on the bench set", "meta": f"generated {e['generated']}",
                    "columns": [col("task", "Task"), col("data", "Footage"), col("detected", "Detected", True),
                                col("delay", "Median delay (s)", True), col("early", "Alarms before onset", True)],
                    "rows": [
                        {"task": "Accident", "data": a["dataset"], "detected": f"{a['detected']} / {a['clips']}",
                         "delay": a["median_delay_s"], "early": a["early_alarms"]},
                        {"task": "Crowd anomaly, all scenes", "data": cr["dataset"], "detected": f"{cr['detected']} / {cr['scenes']}",
                         "delay": cr["median_delay_s"], "early": cr["early_alarms"]},
                        {"task": "Crowd anomaly, held-out scenes only", "data": "UMN scenes 1, 4, 7, 9",
                         "detected": f"{cr['held_out_detected']} / {cr['held_out_scenes']}", "delay": None, "early": None},
                        {"task": "Unattended baggage", "data": b["dataset"], "detected": f"{b['detected']} / {b['clips']}",
                         "delay": None, "early": None},
                    ],
                    "note": "Same settings as the live system. Accident window: 1 s before onset to 10 s after the annotated end. "
                            "ABODA has no onset labels, so baggage has no delay figure."})
        out.append({"title": "False alarms, with and without our filter", "meta": n["dataset"],
                    "columns": [col("scope", "Footage"), col("secs", "Camera-seconds", True),
                                col("without", "Alarms without filter", True), col("with", "Alarms with filter", True),
                                col("rate_without", "Per camera-hour, without", True), col("rate_with", "Per camera-hour, with", True)],
                    "rows": [
                        {"scope": f"Normal clips ({n['clips']})", "secs": n["camera_seconds"], "without": n["alarms_without_filter"],
                         "with": n["false_alarms_with_filter"], "rate_without": n["per_camera_hour_without_filter"],
                         "rate_with": n["per_camera_hour_with_filter"]},
                        {"scope": "All bench footage (incident clips included)", "secs": None,
                         "without": raw_all, "with": raw_all - sup_all,
                         "rate_without": None, "rate_with": None},
                    ],
                    "note": "Without filter = every candidate group an engine produced. With filter = incidents raised after "
                            "persistence, confidence gate and zone checks (groups that passed = total minus suppressed). The normal "
                            "set is under 3 minutes of footage, so the per-hour rates are rough. Crowd persistence was lowered "
                            "from 2 s to 1 s after a first run of this evaluation showed it suppressing real dispersals, so the "
                            "crowd figures here are not from untouched settings."})
    d = load("demo_run")
    if d:
        out.append({"title": "Demo clips", "meta": "what the pipeline raised when the demo cache was built",
                    "columns": [col("cam", "Camera"), col("clip", "Clip"), col("seconds", "Length (s)", True),
                                col("incidents", "Incidents raised"), col("suppressed", "Suppressed", True)],
                    "rows": [{"cam": k, "clip": v["clip"].split("/")[-1], "seconds": v["seconds"],
                              "incidents": "; ".join(f"{i['type']} ({i['subtype']}) at {i['at_s']} s" for i in v["incidents"]) or "none",
                              "suppressed": v["suppressed"]} for k, v in d.items()],
                    "note": "Demo mode replays these cached detections; incidents are rebuilt live from them."})
    return out


HYBRID = {
    "title": "Hybrid plan", "meta": "what we take, from where, and what we build",
    "columns": [col("task", "Task"), col("take", "We take"), col("why", "Why (measured above)"), col("build", "We build")],
    "rows": [
        {"task": "Detection + tracking", "take": "Ultralytics YOLO11n (COCO) exported to OpenVINO, Ultralytics ByteTrack",
         "why": "OpenVINO roughly doubles nano FPS on this CPU; AGPL-3.0 licence is clear",
         "build": "Per-camera workers, shared model, detect-every-N, bags handled outside the tracker"},
        {"task": "Accident", "take": "Enos-123 YOLO11x accident weights (MIT), run on a side thread about once a second",
         "why": "Only accident weights with a licence. The unlicensed nano found more clips but also raised more false alarms",
         "build": "Vehicle-presence check on every model hit, trajectory rule as second opinion and fallback, persistence"},
        {"task": "Crowd", "take": "Nothing from the benched repos beyond the idea of counting people",
         "why": "Count rules flagged calm crowds and missed every dispersal on UMN",
         "build": "Temporal CNN on motion and occupancy features, trained on UMN, plus an overcrowding limit"},
        {"task": "Baggage", "take": "COCO bag classes from the shared detector; owner-proximity idea from the baggage repos",
         "why": "The logic in the benched repo is sound but starved by weak bag detection; the better bag weights have no licence",
         "build": "Position-based bag memory, owner assignment, owner-away timer, tracker-ID handover"},
        {"task": "Incident layer", "take": "Nothing", "why": "No benched repo merges cameras or explains severity",
         "build": "False-alarm filter, severity with reasons, cross-camera merge, operator feedback, evidence clips"},
    ],
    "note": "Unlicensed repos were benched and read, but no file or weight from them ships in this project.",
}


def md_table(sec: dict) -> str:
    cols = sec["columns"]
    lines = [f"### {sec['title']}", ""]
    if sec.get("meta"):
        lines += [f"_{sec['meta']}_", ""]
    lines.append("| " + " | ".join(c["label"] for c in cols) + " |")
    lines.append("|" + "|".join("---:" if c.get("align") == "right" else "---" for c in cols) + "|")
    for r in sec["rows"]:
        lines.append("| " + " | ".join("n/a" if r.get(c["key"]) in (None, "") else str(r[c["key"]]) for c in cols) + " |")
    if sec.get("note"):
        lines += ["", sec["note"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    bench = [s for s in [accident_section(), neyvur_section(), bag_section(), *baria_sections(), saadkhan_section()] if s]
    ours = ours_sections()
    summary = {"generated": time.strftime("%Y-%m-%d %H:%M"), "machine": MACHINE,
               "sections": [HYBRID, *ours, *bench]}
    (RES / "summary.json").write_text(json.dumps(summary, indent=1))
    head = (ROOT / "training" / "bench" / "BENCH_HEAD.md").read_text(encoding="utf-8")
    body = ["## Reference repos, measured", ""] + [md_table(s) for s in bench]
    body += ["## Hybrid plan", "", md_table(HYBRID)]
    body += ["## Our pipeline, measured", ""] + [md_table(s) for s in ours]
    (ROOT / "BENCH.md").write_text(head + "\n" + "\n".join(body), encoding="utf-8")
    # README: the headline tables, injected between markers so they cannot drift from the JSON
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    a, b = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
    if a in text and b in text:
        pick = [s for s in ours if s["title"].startswith(("End to end", "False alarms", "Our crowd model"))]
        nl = chr(10)
        block = nl.join(md_table(s).replace("### ", "**", 1).replace(nl, "**" + nl, 1) for s in pick)
        text = text[:text.index(a) + len(a)] + nl + block + text[text.index(b):]
        readme.write_text(text, encoding="utf-8")
    print(f"summary.json: {len(summary['sections'])} sections; BENCH.md and README results written")


if __name__ == "__main__":
    main()
