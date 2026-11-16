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

# day-one hygiene (lessons.md #4, #7): free disk in GB, transcript retention in days (null = default 30)
disk_free_gb=$(df -k . 2>/dev/null | awk 'NR==2{printf "%d", $4/1048576}')
cleanup_days=$(python3 -c 'import json,os;p=os.path.expanduser("~/.claude/settings.json");print(json.load(open(p)).get("cleanupPeriodDays","null") if os.path.exists(p) else "null")' 2>/dev/null || echo null)
[[ -z "$disk_free_gb" ]] && disk_free_gb=null
[[ "$disk_free_gb" != null && "$disk_free_gb" -lt 50 ]] && echo "WARNING: only ${disk_free_gb} GB free (lessons.md #7)" >&2
[[ "$cleanup_days" == null || "$cleanup_days" -lt 365 ]] 2>/dev/null && echo "WARNING: cleanupPeriodDays is ${cleanup_days} — set >= 365 in ~/.claude/settings.json (lessons.md #4)" >&2

json="$(cat <<JSON
{
  "unity": $(have unity),
  "flutter": $(have flutter),
  "gradle": $(have gradle),
  "node": $(have node),
  "adb": $(have adb),
  "adb_device": $adb_device,
  "python3": $(have python3),
  "disk_free_gb": $disk_free_gb,
  "cleanup_period_days": $cleanup_days
}
JSON
)"

if [[ -n "$OUT" ]]; then
  printf '%s\n' "$json" > "$OUT"
  echo "wrote $OUT"
else
  printf '%s\n' "$json"
fi
