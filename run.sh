#!/usr/bin/env bash
set -euo pipefail

PORT=8000

usage() {
  cat <<EOF
Usage: run.sh [--port PORT]

Starts a simple HTTP server and opens the UI page in your browser.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
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

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="http://localhost:${PORT}/ui/index.html"

echo "Serving ${ROOT} on http://localhost:${PORT}"

cd "$ROOT"
python3 -m http.server "$PORT" &
SERVER_PID=$!
trap 'kill "$SERVER_PID"' EXIT INT TERM

sleep 1

if command -v open >/dev/null; then
  open "$URL"
else
  printf "Please open %s manually\n" "$URL"
fi

wait "$SERVER_PID"
