#!/usr/bin/env bash
# Stops what start.sh / demo.sh / simulate_rtsp.sh started (by saved PID only).
source "$(dirname "$0")/_common.sh"
stop_all
