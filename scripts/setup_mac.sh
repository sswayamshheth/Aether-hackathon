#!/usr/bin/env bash
# One-time setup on macOS (Apple silicon). Run from the project folder:
#   bash scripts/setup_mac.sh
# Needs: Homebrew, Python 3.12 or 3.13, Node 20+, Google Chrome.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v node >/dev/null || brew install node
PY="$(command -v python3.13 || command -v python3.12 || true)"
if [ -z "$PY" ]; then brew install python@3.13; PY="$(command -v python3.13)"; fi

# Python environment (pinned; PyTorch from PyPI includes Apple GPU support)
if [ ! -x backend/.venv/bin/python ]; then "$PY" -m venv backend/.venv; fi
backend/.venv/bin/python -m pip install --upgrade pip -q
backend/.venv/bin/python -m pip install -q -r backend/requirements-mac.txt
backend/.venv/bin/python -c "import torch; print('torch', torch.__version__, '| Apple GPU (mps):', torch.backends.mps.is_available())"

# MediaMTX (RTSP server) for the simulated cameras
if [ ! -x tools/mediamtx/mediamtx ]; then
  mkdir -p tools/mediamtx
  curl -sL -o /tmp/mediamtx.tgz https://github.com/bluenviron/mediamtx/releases/download/v1.21.1/mediamtx_v1.21.1_darwin_arm64.tar.gz
  tar -xzf /tmp/mediamtx.tgz -C tools/mediamtx
fi

# Model weights: skipped if models/ was copied over from the Windows machine
backend/.venv/bin/python training/get_models.py

# Dashboard
(cd frontend && npm ci --no-audit --no-fund && npm run build)
echo
echo "Setup done. Demo mode: bash scripts/demo.sh   Live mode: bash scripts/start.sh"
