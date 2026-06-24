#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-app/scripts/detect-unity.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}

# Build three fixture zips with python's zipfile (portable, no `zip` needed).
mkzip() { python3 - "$1" "${@:2}" <<'PY'
import sys, zipfile
out = sys.argv[1]
with zipfile.ZipFile(out, "w") as z:
    for entry in sys.argv[2:]:
        z.writestr(entry, "x")
PY
}

mkzip "$TMP/il2cpp.apk" "lib/arm64-v8a/libil2cpp.so" "assets/bin/Data/Managed/Metadata/global-metadata.dat"
mkzip "$TMP/mono.apk"   "assets/bin/Data/Managed/Assembly-CSharp.dll"
mkzip "$TMP/plain.apk"  "classes.dex" "AndroidManifest.xml"

check "il2cpp"  "il2cpp" "$(bash "$SCRIPT" "$TMP/il2cpp.apk")"
check "mono"    "mono"   "$(bash "$SCRIPT" "$TMP/mono.apk")"
check "none"    "none"   "$(bash "$SCRIPT" "$TMP/plain.apk")"

bash "$SCRIPT" >/dev/null 2>&1; rc=$?
check "usage exit 2" "2" "$rc"

exit $fail
