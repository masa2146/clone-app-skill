#!/usr/bin/env bash
# Probe build toolchains → JSON capability map on stdout (or --out <file>).
# Branch-agnostic: branch guides read the relevant keys. Never fails the pipeline.
set -uo pipefail

OUT=""
if [[ "${1:-}" == "--out" ]]; then OUT="${2:-}"; fi

have() { command -v "$1" >/dev/null 2>&1 && echo true || echo false; }

adb_device=false
if command -v adb >/dev/null 2>&1; then
  if adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{f=1} END{exit f?0:1}'; then
    adb_device=true
  fi
fi

json="$(cat <<JSON
{
  "unity": $(have unity),
  "flutter": $(have flutter),
  "gradle": $(have gradle),
  "node": $(have node),
  "adb": $(have adb),
  "adb_device": $adb_device,
  "python3": $(have python3)
}
JSON
)"

if [[ -n "$OUT" ]]; then
  printf '%s\n' "$json" > "$OUT"
  echo "wrote $OUT"
else
  printf '%s\n' "$json"
fi
