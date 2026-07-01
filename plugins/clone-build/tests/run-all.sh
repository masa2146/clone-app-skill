#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
fail=0

echo "=== smoke ==="
bash "$HERE/smoke-structure.sh" || fail=1

echo "=== bash tests ==="
for t in "$HERE"/test-*.sh; do
  echo "--- $(basename "$t") ---"
  bash "$t" || fail=1
done

echo "=== python tests ==="
for t in "$HERE"/test-*.py; do
  echo "--- $(basename "$t") ---"
  python3 "$t" || fail=1
done

echo
if [[ "$fail" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit $fail
