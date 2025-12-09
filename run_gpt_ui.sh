#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="config/app.json"
PORT=8000
MODE_OVERRIDE=""
NETLIFY_FLAG=false

usage() {
  cat <<EOF
Usage: run_gpt_ui.sh [--mode real|sample] [--sample] [--real] [--port PORT]

Generates a GPT insight (real or sample depending on mode) and then launches the UI.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE_OVERRIDE="$2"
      shift 2
      ;;
    --sample)
      MODE_OVERRIDE="sample"
      shift
      ;;
    --real)
      MODE_OVERRIDE="real"
      shift
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --netlify)
      NETLIFY_FLAG=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

read_mode() {
  python3 - <<PY
import json
import sys
from pathlib import Path

path = Path("$CONFIG_FILE")
if not path.exists():
    print("real")
    sys.exit(0)
c = json.loads(path.read_text(encoding="utf-8"))
print(c.get("mode", "real"))
PY
}

apply_mode() {
  python3 - <<PY
import json
from pathlib import Path

path = Path("$CONFIG_FILE")
config = {}
if path.exists():
    config = json.loads(path.read_text(encoding="utf-8"))
config["mode"] = "$1"
path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

cleanup_mode() {
  if [[ -n "${REVERT_MODE:-}" ]]; then
    apply_mode "$REVERT_MODE"
  fi
}

prepare_netlify_assets() {
  if [[ "$NETLIFY_FLAG" == "true" ]]; then
    echo "Preparing Netlify assets..."
    mkdir -p ui/config
    cp "$CONFIG_FILE" ui/config/app.json
  fi
}

ORIGINAL_MODE="$(read_mode)"
MODE="${MODE_OVERRIDE:-$ORIGINAL_MODE}"
REVERT_MODE=""
if [[ "$MODE" != "$ORIGINAL_MODE" ]]; then
  apply_mode "$MODE"
  REVERT_MODE="$ORIGINAL_MODE"
fi
trap cleanup_mode EXIT

echo "Generating GPT insight (mode: $MODE)..."
if [[ "$MODE" == "sample" ]]; then
  python3 gpt_insights.py --mode sample
else
  python3 gpt_insights.py
fi

prepare_netlify_assets
echo "Launching UI..."
./run.sh --port "$PORT"
