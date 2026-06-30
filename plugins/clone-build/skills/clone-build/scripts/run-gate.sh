#!/usr/bin/env bash
# Single chokepoint: run one gate command, emit an evidence block, propagate exit.
# Usage: run-gate.sh --kind <build|tdd|visual-diff|launch-crash> --command "<cmd>"
set -uo pipefail

kind=""; command_str=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kind)    kind="${2:-}"; shift 2 ;;
    --command) command_str="${2:-}"; shift 2 ;;
    *) echo "ERROR: unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$kind" in
  build|tdd|visual-diff|launch-crash) ;;
  *) echo "ERROR: --kind must be build|tdd|visual-diff|launch-crash" >&2; exit 2 ;;
esac
if [[ -z "$command_str" ]]; then echo "ERROR: --command required" >&2; exit 2; fi

echo "GATE kind=$kind"
echo "COMMAND: $command_str"
out="$(bash -c "$command_str" 2>&1)"; rc=$?
echo "EXIT: $rc"
echo "---evidence---"
printf '%s\n' "$out"
echo "---end---"
if [[ $rc -eq 0 ]]; then echo "RESULT: PASS"; else echo "RESULT: FAIL"; fi
exit $rc
