#!/usr/bin/env bash
# Live mode on macOS / Linux: RTSP simulation + every model on every camera + dashboard.
#   bash scripts/start.sh            one simulated camera (cam1) - the default on a laptop
#   CAMS=4 bash scripts/start.sh     all four simulated cameras
#   NO_RTSP=1 bash scripts/start.sh  read the clips as files instead of RTSP
set -euo pipefail
source "$(dirname "$0")/_common.sh"
stop_all
SEED=rtsp
if [ "${NO_RTSP:-0}" = "1" ]; then SEED=file
else bash "$ROOT/scripts/simulate_rtsp.sh" || { echo "RTSP failed; reading clips as files"; SEED=file; }
fi
export DRISHTI_DEMO=0 DRISHTI_SEED=$SEED DRISHTI_SEED_COUNT="${CAMS:-1}"
start_backend
open_dashboard
