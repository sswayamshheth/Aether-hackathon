#!/usr/bin/env bash
# Demo mode on macOS / Linux: replays the demo clips with cached detections.
#   bash scripts/demo.sh            (NO_BROWSER=1 to skip opening Chrome)
set -euo pipefail
source "$(dirname "$0")/_common.sh"
[ -f "$ROOT/data/demo/cache/cam1.json" ] || { echo "Demo cache missing: $PY training/prepare_demo.py"; exit 1; }
stop_all
export DRISHTI_DEMO=1 DRISHTI_SEED=
start_backend
open_dashboard
