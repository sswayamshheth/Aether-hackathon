"""Run the synthetic scenario suite through the real pipeline and score it.

    backend\\.venv\\Scripts\\python training\\synth\\run_suite.py [--only <case or category>] [--tag name]
                                                                [--workers N]

Every scenario replays through Pipeline (cache mode) + Runtime: the same engines, false-alarm
filter and incident manager as the live app. Writes docs/results/synthetic_suite[_<tag>].json
with one row per scenario and metrics per category. Method A results are logic-level
(models silent); they are never mixed with real-footage results.
"""
from __future__ import annotations

import heapq
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(ROOT / "models")
os.environ.setdefault("DRISHTI_DB", ":memory:")

import logging  # noqa: E402

logging.disable(logging.WARNING)

SCEN = ROOT / "tests" / "scenarios"
SAMPLE = int(sys.argv[sys.argv.index("--sample") + 1]) if "--sample" in sys.argv else 0
RANK = {"": -1, "Low": 0, "Medium": 1, "High": 2, "Critical": 3}
FAMILY = {"accident_positive": "accident", "traffic_anomaly": "accident", "accident_trap": "accident",
          "crowd_positive": "crowd", "crowd_trap": "crowd", "baggage_positive": "baggage",
          "baggage_trap": "baggage", "baggage_documented": "baggage", "other": "other", "system": "system"}


def load_specs(only: str | None) -> list[dict]:
    specs = []
    for p in sorted(SCEN.rglob("*.yaml")):
        s = yaml.safe_load(p.read_text(encoding="utf-8"))
        if only and not any(o in (s["case"], s["category"], s["id"], FAMILY[s["category"]]) for o in only.split(",")):
            continue
        if SAMPLE and int(s["id"].rsplit("_", 1)[1]) > SAMPLE:
            continue
        specs.append(s)
    return specs


def _threads() -> None:
    import cv2
    import torch

    torch.set_num_threads(1)
    cv2.setNumThreads(1)


def run_one(spec: dict) -> dict:
    try:
        return _run_one(spec)
    except Exception as e:  # one broken scenario must not lose the whole run
        import traceback

        return {"id": spec["id"], "category": spec["category"], "case": spec["case"],
                "family": FAMILY[spec["category"]], "positive": "event" in spec["expected"], "passed": False,
                "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-600:], "why": ["harness error"],
                "delay_s": None, "false_alarms": 0, "conditions": spec["conditions"], "duration_s": 0, "cameras": 1,
                "incidents": [], "suppressed": 0}


def _run_one(spec: dict) -> dict:
    _threads()
    from app.db import Store
    from app.runtime import Pipeline, Runtime
    from generators import GENERATORS
    from sim import background, render_image, render_tracks

    t0 = time.perf_counter()
    rng = random.Random(spec["seed"])
    cond = dict(spec["conditions"])
    g = GENERATORS[spec["generator"]["kind"]](spec["generator"].get("params", {}), cond, rng)
    if "stream_gap_rel" in cond and g.get("t_event") is not None:
        a, b = cond["stream_gap_rel"]
        cond["stream_gap"] = [g["t_event"] + a, g["t_event"] + b]
    store = Store(":memory:")
    rendered = {}
    for k, (cam, info) in enumerate(g["cams"].items()):
        for z in info["world"].zones:
            store.add_zone(cam, z["name"], z["kind"], z["points"])
        rendered[cam] = render_tracks(info["world"], cond, g["duration"], spec["seed"] + k)
    rt = Runtime(store, live=False)
    pipes, heap = {}, []
    for cam, info in g["cams"].items():
        c = {"id": cam, "name": cam, "source": "synthetic", "kind": "file", "area": info["area"], "profile": "all"}
        pipes[cam] = Pipeline(c, rt, fps=float(cond.get("cam_fps", 10.0)), cache=rendered[cam]["frames"])
        for idx, ts in rendered[cam]["timeline"]:
            heap.append((ts, cam, idx))
    heapq.heapify(heap)
    nprng = np.random.default_rng(spec["seed"])
    bgs = {cam: background(spec["seed"] + k) for k, cam in enumerate(g["cams"])}
    last_ts: dict[str, float] = {}
    while heap:
        ts, cam, idx = heapq.heappop(heap)
        if cam in last_ts and ts - last_ts[cam] > 1.5:
            pipes[cam].reset()  # the stream came back after a disconnect, as the RTSP worker does
        last_ts[cam] = ts
        img = render_image(g["cams"][cam]["world"], ts, cond, nprng, bgs[cam])
        pipes[cam].process(img, ts, idx)
    for cam in pipes:
        rt.filter.flush(cam, g["duration"])
    incidents = []
    for h in rt.history:
        row = store.incident(h["id"]) or {}
        cams = row.get("cameras") or []
        if isinstance(cams, str):
            cams = json.loads(cams)
        incidents.append({"id": h["id"], "type": h["type"], "subtype": h["subtype"], "camera": h["camera_id"],
                          "ts": round(h["ts"], 2), "severity": row.get("severity", ""),
                          "score": row.get("score"), "cameras": len(cams)})
    res = score(spec, g, incidents)
    res.update(id=spec["id"], category=spec["category"], case=spec["case"], family=FAMILY[spec["category"]],
               conditions=spec["conditions"], duration_s=g["duration"], cameras=len(g["cams"]),
               incidents=incidents, suppressed=len(rt.suppressed), secs=round(time.perf_counter() - t0, 2))
    return res


def score(spec: dict, g: dict, incs: list[dict]) -> dict:
    exp = spec["expected"]
    out = {"positive": "event" in exp, "passed": True, "why": [], "delay_s": None, "false_alarms": 0,
           "detected_type": None, "severity": None}

    def match(i, e):
        types = e["event"] if isinstance(e["event"], list) else [e["event"]]
        return i["type"] in types and (not e.get("subtype") or e["subtype"] in i["subtype"])

    def check_event(e, t_ref):
        hits = [i for i in incs if match(i, e)]
        lo, hi = t_ref + e["window_s"][0], t_ref + e["window_s"][1]
        good = [i for i in hits if lo <= i["ts"] <= hi]
        early = [i for i in hits if i["ts"] < lo]
        if early:
            out["false_alarms"] += len(early)
            out["why"].append(f"early {e['event']} at {early[0]['ts']:.1f}s (event {t_ref:.1f}s)")
        if not good:
            out["passed"] = False
            late = [i for i in hits if i["ts"] > hi]
            out["why"].append(f"no {e['event']} in [{lo:.1f}, {hi:.1f}]s" +
                              (f", late at {late[0]['ts']:.1f}s" if late else ""))
            return None
        if early:
            out["passed"] = False
        return good

    if "event" in exp:
        good = check_event(exp, g["t_event"])
        if good:
            first = min(good, key=lambda i: i["ts"])
            out.update(delay_s=round(first["ts"] - g["t_event"], 2), detected_type=first["type"],
                       severity=max((i["severity"] for i in good), key=lambda s: RANK.get(s, -1)))
            n = len([i for i in incs if match(i, exp)])
            if exp.get("count") is not None and n != exp["count"]:
                out["passed"] = False
                out["why"].append(f"{n} {exp['event']} incidents, expected {exp['count']}")
                out["false_alarms"] += max(0, n - exp["count"])
            elif exp.get("count") is None and n > 1:
                out["false_alarms"] += n - 1 - len([i for i in incs if match(i, exp) and i["ts"] < g["t_event"] + exp["window_s"][0]])
            if exp.get("min_cameras") and max(i["cameras"] for i in good) < exp["min_cameras"]:
                out["passed"] = False
                out["why"].append(f"merged over {max(i['cameras'] for i in good)} cameras, expected {exp['min_cameras']}")
            if exp.get("min_severity") and RANK.get(out["severity"], -1) < RANK[exp["min_severity"]]:
                out["passed"] = False
                out["why"].append(f"severity {out['severity']}, expected at least {exp['min_severity']}")
        if exp.get("also"):
            a = exp["also"]
            if not check_event(a, g[a["ref"]]):
                pass
    if "forbid" in exp:
        bad = [i for i in incs if i["type"] in exp["forbid"]]
        if bad:
            out["passed"] = False
            out["false_alarms"] += len(bad)
            out["why"].append(f"{len(bad)} {bad[0]['type']} alarm(s), first at {bad[0]['ts']:.1f}s ({bad[0]['subtype']})")
    if "forbid_above" in exp:
        for typ, lvl in exp["forbid_above"].items():
            bad = [i for i in incs if i["type"] == typ and RANK.get(i["severity"], -1) > RANK[lvl]]
            if bad:
                out["passed"] = False
                out["false_alarms"] += len(bad)
                out["why"].append(f"{typ} alarm at {bad[0]['severity']} severity ({bad[0]['subtype']}) at {bad[0]['ts']:.1f}s")
    return out


def metrics(rows: list[dict]) -> dict:
    fam: dict[str, dict] = {}
    for r in rows:
        if r.get("error"):
            continue
        m = fam.setdefault(r["family"], {"scenarios": 0, "passed": 0, "tp": 0, "fn": 0, "fp": 0,
                                         "delays": [], "fa": 0, "neg_hours": 0.0})
        m["scenarios"] += 1
        m["passed"] += r["passed"]
        if r["positive"]:
            if r["delay_s"] is not None:
                m["tp"] += 1
                m["delays"].append(r["delay_s"])
            else:
                m["fn"] += 1
            m["fp"] += r["false_alarms"]
        else:
            m["fp"] += r["false_alarms"]
            m["fa"] += r["false_alarms"]
            m["neg_hours"] += r["duration_s"] * r["cameras"] / 3600
    out = {}
    for k, m in sorted(fam.items()):
        p = m["tp"] / (m["tp"] + m["fp"]) if m["tp"] + m["fp"] else None
        rc = m["tp"] / (m["tp"] + m["fn"]) if m["tp"] + m["fn"] else None
        f1 = 2 * p * rc / (p + rc) if p and rc else (0.0 if p is not None and rc is not None else None)
        out[k] = {"scenarios": m["scenarios"], "pass_rate": round(m["passed"] / m["scenarios"], 3),
                  "precision": None if p is None else round(p, 3), "recall": None if rc is None else round(rc, 3),
                  "f1": None if f1 is None else round(f1, 3),
                  "mean_delay_s": round(float(np.mean(m["delays"])), 2) if m["delays"] else None,
                  "false_alarms_on_traps": m["fa"],
                  "false_alarms_per_camera_hour": round(m["fa"] / m["neg_hours"], 1) if m["neg_hours"] else None}
    out["all"] = {"scenarios": len(rows), "pass_rate": round(sum(r["passed"] for r in rows) / max(1, len(rows)), 3)}
    return out


def main() -> None:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 1
    specs = load_specs(only)
    t0 = time.time()
    if workers > 1:
        from multiprocessing import Pool

        rows = []
        part = ROOT / ".cache" / f"suite_partial_{tag or 'run'}.jsonl"
        with Pool(workers) as pool, open(part, "w") as fp:
            for r in pool.imap_unordered(run_one, specs, chunksize=2):
                rows.append(r)
                fp.write(json.dumps(r, default=str) + "\n")
                fp.flush()
        rows.sort(key=lambda r: r["id"])
    else:
        rows = []
        for s in specs:
            rows.append(run_one(s))
            r = rows[-1]
            if "--verbose" in sys.argv:
                print(f"{r['id']:34s} {'PASS' if r['passed'] else 'FAIL'} {r['secs']:5.1f}s {'; '.join(r['why'])}",
                      flush=True)
    m = metrics(rows)
    from app import config

    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "method": "A: trajectory-level, models silent (synthetic)",
           "settings": {"gate": config.GATE, "persist_s": config.PERSIST_S, "min_hits": config.MIN_HITS,
                        "bag_unattended_s": config.BAG_UNATTENDED_S, "crowd_limit": config.CROWD_LIMIT},
           "metrics": m, "runtime_s": round(time.time() - t0, 1), "rows": rows}
    name = f"synthetic_suite{'_' + tag if tag else ''}.json"
    if not only or tag:
        (ROOT / "docs" / "results" / name).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(m, indent=None))
    fails: dict[str, int] = {}
    for r in rows:
        if not r["passed"]:
            fails[r["case"]] = fails.get(r["case"], 0) + 1
    errs = [r["id"] for r in rows if r.get("error")]
    if errs:
        print("HARNESS ERRORS:", errs[:10], len(errs))
    print("failing cases:", dict(sorted(fails.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
