#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-build/scripts/run-gate.sh"
fail=0
check() { local d="$1" e="$2" a="$3"; if [[ "$e" == "$a" ]]; then echo "PASS: $d"; else echo "FAIL: $d — expected '$e' got '$a'"; fail=1; fi; }

out="$(bash "$SCRIPT" --kind build --command true)"; rc=$?
check "pass exit 0" "0" "$rc"
echo "$out" | grep -q "RESULT: PASS" && check "pass result line" 1 1 || check "pass result line" 1 0

out="$(bash "$SCRIPT" --kind tdd --command false)"; rc=$?
check "fail exit 1" "1" "$rc"
echo "$out" | grep -q "RESULT: FAIL" && check "fail result line" 1 1 || check "fail result line" 1 0

echo "$out" | grep -q -- "---evidence---" && check "evidence block" 1 1 || check "evidence block" 1 0

bash "$SCRIPT" --kind bogus --command true >/dev/null 2>&1; check "bad kind exit 2" "2" "$?"
bash "$SCRIPT" --kind build >/dev/null 2>&1; check "missing command exit 2" "2" "$?"

exit $fail
