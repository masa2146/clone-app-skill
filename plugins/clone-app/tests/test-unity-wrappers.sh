#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-app/scripts"
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}

# usage errors → exit 2
bash "$S/il2cpp-dump.sh" >/dev/null 2>&1; check "il2cpp usage" "2" "$?"
bash "$S/unity-assets.sh" >/dev/null 2>&1; check "assets usage" "2" "$?"

# tool missing → exit 3 + guidance text on stderr
err="$(IL2CPP_INSPECTOR_CLI=/no/such/bin bash "$S/il2cpp-dump.sh" a b c 2>&1 >/dev/null)"; rc=$?
check "il2cpp missing exit 3" "3" "$rc"
grep -q "Il2CppInspectorRedux" <<<"$err" && echo "PASS: il2cpp guidance" || { echo "FAIL: il2cpp guidance"; fail=1; }

err="$(ASSETRIPPER_CLI=/no/such/bin bash "$S/unity-assets.sh" a b 2>&1 >/dev/null)"; rc=$?
check "assets missing exit 3" "3" "$rc"
grep -q "AssetRipper" <<<"$err" && echo "PASS: assets guidance" || { echo "FAIL: assets guidance"; fail=1; }

exit $fail
