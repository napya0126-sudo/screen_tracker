#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/logs/tracker.pid"
OUT_LOG="$ROOT_DIR/logs/tracker_stdout.log"

mkdir -p "$ROOT_DIR/logs"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" >/dev/null 2>&1; then
    echo "Tracker is already running. PID=$PID"
    exit 0
  else
    rm -f "$PID_FILE"
  fi
fi

cd "$ROOT_DIR"
nohup python3 src/tracker.py >>"$OUT_LOG" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" >"$PID_FILE"

echo "Tracker started. PID=$NEW_PID"
echo "Record log: $ROOT_DIR/logs/activity_log.jsonl"
echo "Process log: $OUT_LOG"
