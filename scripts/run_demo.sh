#!/usr/bin/env bash
# Unified demo: sync viewer data, launch agents, serve the static viewer.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VIEWER_PORT="${VIEWER_PORT:-8080}"
BAND_ROOM_URL="${BAND_ROOM_URL:-${DFIR_BAND_ROOM_URL:-https://app.band.ai/}}"
SYNC_INTERVAL="${SYNC_INTERVAL:-5}"

AGENTS_PID=""
HTTP_PID=""
SYNC_PID=""

discover_case_dir() {
  local latest=""
  local latest_mtime=0
  local chain mtime dir name
  for chain in data/outputs/*/audit_chain.jsonl; do
    [[ -f "$chain" ]] || continue
    dir="$(dirname "$chain")"
    name="$(basename "$dir")"
    [[ "$name" == *.backup ]] && continue
    mtime=$(stat -c %Y "$chain" 2>/dev/null || stat -f %m "$chain")
    if (( mtime > latest_mtime )); then
      latest_mtime=$mtime
      latest="$dir"
    fi
  done
  echo "$latest"
}

has_case_sealed() {
  local chain="$1/audit_chain.jsonl"
  [[ -f "$chain" ]] && grep -q '"event_type": "CASE_SEALED"' "$chain" 2>/dev/null
}

build_and_copy_case_file() {
  local src="$1"
  local case_id
  case_id="$(basename "$src")"
  python -c "
from pathlib import Path
import json
from lib.case_brief import build_case_file

case_id = ${case_id@Q}
cf = build_case_file(case_id, outputs_dir='data/outputs')
Path('viewer/data/case_001_output.json').write_text(
    json.dumps(cf, indent=2) + '\n', encoding='utf-8'
)
"
}

sync_viewer_data() {
  local src="${1:-$(discover_case_dir)}"
  local dst="viewer/data"
  local quiet="${2:-0}"
  mkdir -p "$dst"

  if [[ -z "$src" || ! -f "$src/audit_chain.jsonl" ]]; then
    [[ "$quiet" -eq 0 ]] && echo "Note: no active case with audit_chain.jsonl under data/outputs/ yet"
    return 0
  fi

  cp "$src/audit_chain.jsonl" "$dst/case_001_audit.jsonl"
  [[ "$quiet" -eq 0 ]] && echo "Synced $src/audit_chain.jsonl -> $dst/case_001_audit.jsonl"

  if has_case_sealed "$src"; then
    if [[ -f "$src/case_file.json" ]]; then
      cp "$src/case_file.json" "$dst/case_001_output.json"
      [[ "$quiet" -eq 0 ]] && echo "Synced $src/case_file.json -> $dst/case_001_output.json"
    else
      build_and_copy_case_file "$src"
      [[ "$quiet" -eq 0 ]] && echo "Built case_file from $src -> $dst/case_001_output.json"
    fi
  fi
}

sync_loop() {
  while true; do
    sync_viewer_data "" 1 || true
    sleep "$SYNC_INTERVAL" || true
  done
}

cleanup() {
  echo ""
  echo "Stopping demo..."
  if [[ -n "$SYNC_PID" ]] && kill -0 "$SYNC_PID" 2>/dev/null; then
    kill -TERM "$SYNC_PID" 2>/dev/null || true
    wait "$SYNC_PID" 2>/dev/null || true
  fi
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

sync_loop &
SYNC_PID=$!

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
echo " Sync:      every ${SYNC_INTERVAL}s from latest data/outputs/*/"
echo "================================================="
echo " Press Ctrl+C to stop agents, viewer, and sync loop."
echo ""

while kill -0 "$AGENTS_PID" 2>/dev/null || kill -0 "$HTTP_PID" 2>/dev/null || kill -0 "$SYNC_PID" 2>/dev/null; do
  wait -n "$AGENTS_PID" "$HTTP_PID" "$SYNC_PID" 2>/dev/null || sleep 1
done

cleanup
