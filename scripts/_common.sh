# Shared helpers for the macOS / Linux scripts. Sourced, not run.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
CACHE="$ROOT/.cache"
mkdir -p "$CACHE"
export YOLO_CONFIG_DIR="$CACHE/ultralytics" HF_HOME="$CACHE/hf" HF_HUB_OFFLINE=1 PYTHONIOENCODING=utf-8
# some operations are not implemented on Apple GPUs yet; let PyTorch fall back to CPU for those
export PYTORCH_ENABLE_MPS_FALLBACK=1

stop_all() {
  for f in "$CACHE/rtsp_pids.txt" "$CACHE/backend_pid.txt"; do
    [ -f "$f" ] || continue
    while read -r pid; do
      [ -n "$pid" ] && kill "$pid" 2>/dev/null && echo "stopped $pid"
    done < "$f"
    : > "$f"
  done
}

start_backend() {
  [ -x "$PY" ] || { echo "Run bash scripts/setup_mac.sh first"; exit 1; }
  [ -f "$ROOT/frontend/dist/index.html" ] || (cd "$ROOT/frontend" && npm ci --no-audit --no-fund && npm run build)
  (cd "$ROOT/backend" && nohup "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning \
      > "$CACHE/backend.out.log" 2> "$CACHE/backend.log" & echo $! > "$CACHE/backend_pid.txt")
  echo "backend starting (pid $(cat "$CACHE/backend_pid.txt")), log: .cache/backend.log"
  for _ in $(seq 1 120); do
    sleep 1
    if curl -s -m 2 http://127.0.0.1:8000/api/status > /dev/null; then
      curl -s http://127.0.0.1:8000/api/status; echo; return 0
    fi
  done
  echo "Backend did not answer within 120 s. See .cache/backend.log"; exit 1
}

open_dashboard() {
  if [ "${NO_BROWSER:-0}" != "1" ]; then
    open -a "Google Chrome" http://localhost:8000 2>/dev/null || echo "Open http://localhost:8000 in Chrome"
  fi
  echo "Dashboard: http://localhost:8000   Stop: bash scripts/stop.sh"
}
