#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
export KEYBOARD_WRAPPED_ROOT="$(pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
export KEYBOARD_WRAPPED_PYTHON="$PYTHON_BIN"

MODE="real"
LOG_MODE=""
GPT_LOOP=""
MONITOR_MODE=""
RESET_STATS=""

cleanup_pidfile() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    if [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pidfile"
  fi
}

cleanup() {
  cleanup_pidfile "mac-widget/.widget_gpt.pid"
  cleanup_pidfile "mac-widget/.keyboard_logger.pid"
}

kill_helpers() {
  pkill -f keyboard_logger.py >/dev/null 2>&1 || true
  pkill -f scripts/widget_gpt.py >/dev/null 2>&1 || true
}

trap '
  cleanup
  kill_helpers
' EXIT INT TERM
NO_GPT_LOOP=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sample)
      MODE="sample"
      shift
      ;;
    --log)
      LOG_MODE="--log"
      shift
      ;;
    --no-gpt)
      NO_GPT_LOOP="1"
      shift
      ;;
    --help|-h)
      echo "Usage: run_menu_app.sh [--sample] [--log] [--gpt-loop] [--monitor] [--reset]"
      exit 0
      ;;
    --monitor)
      MONITOR_MODE="1"
      shift
      ;;
    --reset)
      RESET_STATS="1"
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

load_api_key() {
  local keyfile="config/gpt_key.json"
  if [[ ! -f "$keyfile" ]]; then
    echo "widget-gpt key file missing" >> data/widget_debug.log
    return
  fi
  local key
  key=$(python3 - <<'PY'
import json, pathlib, sys
path = pathlib.Path("config/gpt_key.json")
try:
    data = json.loads(path.read_text())
    sys.stdout.write(data.get("api_key", ""))
except Exception as exc:
    sys.stderr.write(f"keyfile load error: {exc}")
    sys.exit(0)
PY
  )
  if [[ -n "$key" ]]; then
    export OPENAI_API_KEY="$key"
    python3 - <<'PY' >/dev/null 2>&1
import pathlib
from datetime import datetime
path = pathlib.Path("data/widget_debug.log")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(f"{datetime.utcnow():%Y-%m-%d %H:%M:%S} loaded api key from config/gpt_key.json\n", encoding="utf-8")
PY
  else
    echo "widget-gpt key file empty" >> data/widget_debug.log
  fi
}

export KEYBOARD_WRAPPED_MODE="$MODE"
if [[ "$MONITOR_MODE" == "1" ]]; then
  export KEYBOARD_WRAPPED_MONITOR="1"
else
  unset KEYBOARD_WRAPPED_MONITOR
fi
load_api_key

if [[ "$RESET_STATS" == "1" ]]; then
  echo "Stopping any running helpers before resetting stats..."
  kill_helpers
  echo "Resetting daily stats..."
  python3 scripts/reset_summary.py --mode "$MODE" --root "$KEYBOARD_WRAPPED_ROOT"
fi

ensure_logger() {
  if [[ "$MODE" == "sample" ]]; then
    return
  fi
  if pgrep -f "keyboard_logger.py" >/dev/null; then
    return
  fi
  echo "Starting keyboard logger for live data..."
  nohup python3 keyboard_logger.py --summary data/summary.json ${LOG_MODE} >/tmp/keyboard_logger.log 2>&1 &
  echo $! > mac-widget/.keyboard_logger.pid
}

ensure_progress() {
  echo "Ensuring widget progress snapshot exists..."
  python3 - <<PY
import json
from pathlib import Path
from scripts.widget_refresh import persist_widget_progress

root = Path("$KEYBOARD_WRAPPED_ROOT")
mode = "$MODE"
summary_path = root / ("data/sample_summary.json" if mode == "sample" else "data/summary.json")
progress_path = root / "data/widget_progress.json"
progress_path.parent.mkdir(parents=True, exist_ok=True)
# persist copy ignoring failures
try:
    persist_widget_progress(summary_path, progress_path, mode=mode)
except Exception as exc:
    print(f"widget progress sync failed: {exc}")
PY
}

ensure_logger
if [[ "$NO_GPT_LOOP" != "1" ]]; then
  echo "Widget GPT bridge will refresh only when the menu opens."
else
  echo "GPT bridge loop disabled; the widget will use the latest stored insight."
fi

run_gpt_insight_once() {
  echo "Generating AI insight via gpt_insights.py (mode $MODE)..."
  "$PYTHON_BIN" gpt_insights.py --mode "$MODE" >/tmp/gpt_insight.log 2>&1 || true
}

ensure_gpt_feed() {
  echo "Ensuring widget GPT feed exists..."
  "$PYTHON_BIN" - <<PY
import json
from pathlib import Path

root = Path("$KEYBOARD_WRAPPED_ROOT")
feed_path = root / "data/widget_gpt_feed.json"
feed_path.parent.mkdir(parents=True, exist_ok=True)
if not feed_path.exists():
    feed_path.write_text(
        json.dumps(
            {"timestamp": 0, "mode": "$MODE", "analysis_text": "Awaiting AI insight…", "diff": [], "progress": {}},
            indent=2,
        )
    )
PY
}

run_gpt_insight_once
ensure_progress
ensure_gpt_feed

if [[ ! -f "mac-widget/.build/release/KeyboardMonitor" ]]; then
  echo "Build missing, running release build..."
  "$SCRIPT_DIR/build_menu_app.sh"
fi

cd mac-widget

echo "Launching KeyboardMonitor in $MODE mode..."
./.build/release/KeyboardMonitor
