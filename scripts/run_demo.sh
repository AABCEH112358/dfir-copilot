#!/usr/bin/env bash
# Unified demo: sync viewer data, launch agents, serve the static viewer.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VIEWER_PORT="${VIEWER_PORT:-8080}"
BAND_ROOM_URL="${BAND_ROOM_URL:-${DFIR_BAND_ROOM_URL:-https://app.band.ai/}}"

AGENTS_PID=""
HTTP_PID=""

sync_viewer_data() {
  local src="data/outputs/DFIR-2026-001"
  local dst="viewer/data"
  mkdir -p "$dst"

  if [[ -f "$src/case_file.json" ]]; then
    cp "$src/case_file.json" "$dst/case_001_output.json"
    echo "Synced $src/case_file.json -> $dst/case_001_output.json"
  else
    echo "Note: $src/case_file.json not found — viewer will use existing viewer/data/case_001_output.json"
  fi

  if [[ -f "$src/audit_chain.jsonl" ]]; then
    cp "$src/audit_chain.jsonl" "$dst/case_001_audit.jsonl"
    echo "Synced $src/audit_chain.jsonl -> $dst/case_001_audit.jsonl"
  else
    echo "Note: $src/audit_chain.jsonl not found — viewer will use existing viewer/data/case_001_audit.jsonl"
  fi
}

cleanup() {
  echo ""
  echo "Stopping demo..."
  if [[ -n "$AGENTS_PID" ]] && kill -0 "$AGENTS_PID" 2>/dev/null; then
    kill -TERM "$AGENTS_PID" 2>/dev/null || true
    wait "$AGENTS_PID" 2>/dev/null || true
  fi
  if [[ -n "$HTTP_PID" ]] && kill -0 "$HTTP_PID" 2>/dev/null; then
    kill -TERM "$HTTP_PID" 2>/dev/null || true
    wait "$HTTP_PID" 2>/dev/null || true
  fi
  echo "Demo stopped."
  exit 0
}

trap cleanup INT TERM

if [[ -f venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source venv/bin/activate
fi

sync_viewer_data

echo "Starting agents..."
python scripts/run_all.py &
AGENTS_PID=$!

sleep 4

echo "Starting viewer HTTP server on port ${VIEWER_PORT}..."
(cd viewer && python -m http.server "$VIEWER_PORT") &
HTTP_PID=$!

VIEWER_URL="http://localhost:${VIEWER_PORT}/index.html"

echo ""
echo "================================================="
echo " DFIR Investigator — Unified Demo"
echo "================================================="
echo " Viewer:    ${VIEWER_URL}"
echo " Band room: ${BAND_ROOM_URL}"
echo "================================================="
echo " Press Ctrl+C to stop agents and viewer."
echo ""

while kill -0 "$AGENTS_PID" 2>/dev/null || kill -0 "$HTTP_PID" 2>/dev/null; do
  wait -n "$AGENTS_PID" "$HTTP_PID" 2>/dev/null || sleep 1
done

cleanup
