"""Write SYNTHETIC_SCENARIOS.md from the spec files and the latest results.

    backend\\.venv\\Scripts\\python training\\synth\\write_docs.py [suite_json] [pixel_json]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCEN = ROOT / "tests" / "scenarios"
RES = ROOT / "docs" / "results"


def exp_text(e: dict) -> str:
    if "forbid" in e:
        return "no " + " / ".join(e["forbid"]) + " incident"
    if "forbid_above" in e:
        return "; ".join(f"no {t} incident above {lvl} severity" for t, lvl in e["forbid_above"].items())
    ev = e["event"] if isinstance(e["event"], str) else " or ".join(e["event"])
    w = e.get("window_s")
    s = f"{ev}" + (f" ({e['subtype']})" if e.get("subtype") else "")
    if isinstance(w, list):
        s += f", raised between t{w[0]:+g} s and t{w[1]:+g} s of the scripted event"
    if e.get("count"):
        s += f", exactly {e['count']} incident(s)"
    if e.get("min_cameras"):
        s += f", merged across at least {e['min_cameras']} cameras"
    if e.get("min_severity"):
        s += f", severity at least {e['min_severity']}"
    if e.get("also"):
        s += f"; plus a {e['also']['event']} incident on the second camera"
    if e.get("note"):
        s += f" ({e['note']})"
    return s


def main() -> None:
    suite = Path(sys.argv[1]) if len(sys.argv) > 1 else RES / "synthetic_suite_baseline.json"
    pixel = Path(sys.argv[2]) if len(sys.argv) > 2 else RES / "synthetic_pixel.json"
    rows = {r["id"]: r for r in json.loads(suite.read_text())["rows"]} if suite.exists() else {}
    prow = {r["id"]: r for r in json.loads(pixel.read_text())["rows"]} if pixel.exists() else {}
    cases: dict[tuple, list] = defaultdict(list)
    for p in sorted(SCEN.rglob("*.yaml")):
        s = yaml.safe_load(p.read_text(encoding="utf-8"))
        cases[(s["category"], s.get("case", s["id"].split("__")[0]))].append(s)
    counts = defaultdict(int)
    for (cat, _), specs in cases.items():
        counts[cat] += len(specs)
    L = ["# SYNTHETIC_SCENARIOS.md", "",
         "Every synthetic scenario, how it is generated and what the system is expected to do. Spec files live in",
         "`tests/scenarios/<category>/<id>.yaml`; results are in `docs/results/synthetic_suite*.json` (method A) and",
         "`docs/results/synthetic_pixel*.json` (method B). **Synthetic results are never mixed with real results.**", "",
         "Methods", "",
         "- **A, trajectory-level** (`training/synth/`): scripted boxes for people, vehicles and bags, turned into",
         "  detector-like output (misses, jitter, ID switches, occlusion gaps, detection rate, camera shake, lower",
         "  confidence at night / in rain / fog) and replayed through the real Pipeline, filter and incident manager.",
         "  The vision models are silent, so A tests the logic: rules, timing, thresholds, severity and cross-camera merge.",
         "- **B, pixel-level**: real labelled clips re-run through the full detector + tracker + engines with an image",
         "  condition on every frame (night, rain, fog, JPEG q10, low resolution, motion blur, shake, noise, infrared",
         "  grayscale, dropped frames, an occluding mask). Ground truth carries over from the real labels.",
         "- **C, composited baggage scenes**: not built tonight (see OVERNIGHT_REPORT.md, known gaps). Baggage timing",
         "  cases are covered by method A instead.", "",
         "Every method A case runs in ten condition variants: day/night, clear/rain/fog, low/medium/high density,",
         "near/mid/far, camera angle 0-90 degrees, with or without occlusion gaps, 3/5/10 detections per second, ID",
         "switches, jitter and shake.", "", "## Counts", "", "| Category | Scenarios |", "|---|---|"]
    for cat in sorted(counts):
        L.append(f"| {cat} | {counts[cat]} |")
    L.append(f"| **total** | **{sum(counts.values())}** |")
    L += ["", "## Scenarios", "", "| Category | Case | Method | Variants | Generated as | Expected outcome | Passing (latest run) |",
          "|---|---|---|---|---|---|---|"]
    for (cat, case), specs in sorted(cases.items()):
        s0 = specs[0]
        res = [rows.get(s["id"]) or prow.get(s["id"]) for s in specs]
        res = [r for r in res if r]
        passing = f"{sum(r['passed'] for r in res)}/{len(res)}" if res else "not run"
        m = "A" if s0["method"].startswith("A") else "B"
        L.append(f"| {cat} | {case} | {m} | {len(specs)} | {s0['description']} | {exp_text(s0['expected'])} | {passing} |")
    (ROOT / "SYNTHETIC_SCENARIOS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote SYNTHETIC_SCENARIOS.md", sum(counts.values()), "scenarios")


if __name__ == "__main__":
    main()
