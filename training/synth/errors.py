"""Group synthetic-suite failures into clusters by cause and write ERRORS.md.

    backend\\.venv\\Scripts\\python training\\synth\\errors.py [suite_json]

Cause labels are assigned from what the run recorded, not guessed per scenario by hand:
  missed (rule gap)      positive case with no candidate for the expected type at all
  missed (suppressed)    candidates existed but the filter held them back (threshold / persistence)
  late (timing)          raised, but after the expected window
  early / duplicate      raised before the event or more than once
  false alarm (trap)     a trap scenario raised the forbidden type
  severity / merge       raised in time but severity or camera merge was wrong
Each failure is also tagged with the conditions that differ from the day/clear/near default,
so a cluster shows whether night, distance, occlusion or detection rate is behind it.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def cause(r: dict) -> str:
    why = " ".join(r["why"])
    if not r["positive"]:
        return "false alarm (trap)"
    if "late at" in why:
        return "late (timing)"
    if "early" in why or "incidents, expected" in why and r["delay_s"] is not None:
        return "early / duplicate"
    if "severity" in why or "merged over" in why:
        return "severity / merge"
    if "incidents, expected" in why:
        return "count (merge or split)"
    if r.get("suppressed"):
        return "missed (suppressed by filter)"
    return "missed (rule gap: no candidate)"


def tags(c: dict) -> list[str]:
    t = []
    if c.get("light") == "night":
        t.append("night")
    if c.get("weather") in ("rain", "fog"):
        t.append(c["weather"])
    if c.get("distance") == "far":
        t.append("far/small objects")
    if c.get("occlusion") == "partial":
        t.append("occlusion")
    if c.get("id_switch"):
        t.append("ID switch")
    if float(c.get("fps", 5)) <= 3:
        t.append("<=3 detections/s")
    if c.get("shake"):
        t.append("shake")
    return t or ["clean conditions"]


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "results" / "synthetic_suite_baseline.json"
    d = json.loads(path.read_text())
    fails = [r for r in d["rows"] if not r["passed"]]
    clusters: dict[tuple, list] = defaultdict(list)
    for r in fails:
        clusters[(r["case"], cause(r))].append(r)
    ranked = sorted(clusters.items(), key=lambda kv: -len(kv[1]))
    L = ["# ERRORS.md - synthetic suite failure clusters", "",
         f"Source: `{path.relative_to(ROOT)}` ({d['generated']}), {len(d['rows'])} scenarios, {len(fails)} failing.",
         "Method A (trajectory-level, models silent): these are logic failures, not vision failures. Real-footage",
         "errors are in docs/results/real_eval*.json and are reported separately.", "",
         "## Failures by cause", "", "| Cause | Failures |", "|---|---|"]
    for k, v in Counter(cause(r) for r in fails).most_common():
        L.append(f"| {k} | {v} |")
    L += ["", "## Clusters, largest first", "", "| # | Case | Cause | Count | Conditions in the failures | Example |",
          "|---|---|---|---|---|---|"]
    for i, ((case, cz), rs) in enumerate(ranked, 1):
        tc = Counter(t for r in rs for t in tags(r["conditions"]))
        ex = rs[0]
        L.append(f"| {i} | {case} | {cz} | {len(rs)} | {', '.join(f'{k} {v}' for k, v in tc.most_common(4))} | "
                 f"{ex['id']}: {'; '.join(ex['why'])} |")
    (ROOT / "ERRORS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12 + len(ranked) + 8]))


if __name__ == "__main__":
    main()
