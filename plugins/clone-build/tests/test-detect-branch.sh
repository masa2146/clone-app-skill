#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-build/scripts/detect-branch.sh"
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}

check "app+flutter" "app flutter"  "$(bash "$SCRIPT" "$HERE/fixtures/spec-app.md")"
check "game+unity"  "game unity"    "$(bash "$SCRIPT" "$HERE/fixtures/spec-game.md")"

bash "$SCRIPT" >/dev/null 2>&1; check "usage exit 2" "2" "$?"
bash "$SCRIPT" "$HERE/fixtures/does-not-exist.md" >/dev/null 2>&1; check "missing exit 2" "2" "$?"

exit $fail
