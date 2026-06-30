#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-build/scripts/preflight.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fail=0
check() { local d="$1" c="$2"; if [[ "$c" == "1" ]]; then echo "PASS: $d"; else echo "FAIL: $d"; fail=1; fi; }

# Mock a PATH where `flutter` exists but `gradle` does not.
mkdir -p "$TMP/bin"
printf '#!/usr/bin/env bash\nexit 0\n' > "$TMP/bin/flutter"; chmod +x "$TMP/bin/flutter"
out="$(PATH="$TMP/bin:/usr/bin:/bin" bash "$SCRIPT")"
echo "$out"
python3 - "$out" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
assert d["flutter"] is True, "flutter should be true"
assert d["gradle"] is False, "gradle should be false"
for k in ["unity","flutter","gradle","node","adb","adb_device","python3"]:
    assert k in d, f"missing key {k}"
print("ok")
PY
check "valid JSON with expected keys/values" "$([[ $? -eq 0 ]] && echo 1)"

# --out writes a file
PATH="$TMP/bin:/usr/bin:/bin" bash "$SCRIPT" --out "$TMP/pf.json" >/dev/null
[[ -s "$TMP/pf.json" ]] && check "--out wrote file" 1 || check "--out wrote file" 0

exit $fail
