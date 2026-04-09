#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/logs/tracker.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Tracker is not running (pid file not found)."
  exit 0
fi

PID="$(cat "$PID_FILE")"

if kill -0 "$PID" >/dev/null 2>&1; then
  kill "$PID"
  rm -f "$PID_FILE"
  echo "Tracker stopped. PID=$PID"
else
  rm -f "$PID_FILE"
  echo "Tracker process was not running. Removed stale pid file."
fi
