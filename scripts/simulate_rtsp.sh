#!/usr/bin/env bash
# Publishes the demo clips as looping RTSP streams: rtsp://localhost:8554/cam1 .. cam4
set -euo pipefail
source "$(dirname "$0")/_common.sh"
MTX="$ROOT/tools/mediamtx/mediamtx"
[ -x "$MTX" ] || { echo "MediaMTX missing: run bash scripts/setup_mac.sh"; exit 1; }
FF="$(command -v ffmpeg || true)"
[ -n "$FF" ] || { echo "ffmpeg missing: brew install ffmpeg"; exit 1; }
: > "$CACHE/rtsp_pids.txt"
(cd "$ROOT/tools/mediamtx" && nohup ./mediamtx mediamtx.yml > "$CACHE/mediamtx.log" 2>&1 & echo $! >> "$CACHE/rtsp_pids.txt")
sleep 2
"$PY" - "$ROOT" <<'EOF' | while IFS='|' read -r clip url; do
import json, sys
for c in json.load(open(sys.argv[1] + "/scripts/cameras.json"))["cameras"]:
    print(f"{sys.argv[1]}/{c['clip']}|{c['rtsp']}")
EOF
  [ -f "$clip" ] || { echo "missing $clip"; continue; }
  nohup "$FF" -v error -re -stream_loop -1 -i "$clip" -an -c:v libx264 -preset ultrafast -tune zerolatency \
      -g 20 -pix_fmt yuv420p -f rtsp -rtsp_transport tcp "$url" > /dev/null 2>&1 &
  echo $! >> "$CACHE/rtsp_pids.txt"
  echo "publishing $url"
done
