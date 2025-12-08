#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8000
SOURCE="real"

usage() {
  cat <<EOF
Usage: run.sh [--sample|--real] [--port PORT]

Starts a simple HTTP server and opens the UI page in your browser.
--sample  open the UI + query flag so it loads the sample dataset.
--real    open the UI against your real data (default).
--port    override the HTTP server port.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sample)
      SOURCE="sample"
      shift
      ;;
    --real)
      SOURCE="real"
      shift
      ;;
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

cd "$ROOT"

URL="http://localhost:${PORT}/ui/index.html"
if [[ "$SOURCE" == "sample" ]]; then
  URL="${URL}?data=sample"
fi

echo "Serving $(pwd) on http://localhost:${PORT} ($SOURCE data)"

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
