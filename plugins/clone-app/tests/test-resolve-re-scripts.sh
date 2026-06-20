#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/resolve-re-scripts.sh"
fail=0
check() { [[ "$2" == "$3" ]] && echo "PASS: $1" || { echo "FAIL: $1 — expected '$2' got '$3'"; fail=1; }; }

# In the real repo layout, the RE scripts dir exists as a sibling plugin.
out="$(bash "$SCRIPT" 2>/dev/null)"; rc=$?
check "exit 0 when RE present" "0" "$rc"
check "ends with scripts dir" "android-reverse-engineering/skills/android-reverse-engineering/scripts" \
  "$(basename "$(dirname "$(dirname "$(dirname "$out")")")")/$(basename "$(dirname "$(dirname "$out")")")/$(basename "$(dirname "$out")")/$(basename "$out")"
check "decompile.sh exists under resolved dir" "yes" \
  "$([[ -f "$out/decompile.sh" ]] && echo yes || echo no)"

# When CLAUDE_PLUGIN_ROOT points somewhere with no sibling RE plugin → exit 1
tmp="$(mktemp -d)"
out2="$(CLAUDE_PLUGIN_ROOT="$tmp/clone-app" bash "$SCRIPT" 2>/dev/null)"; rc2=$?
check "exit 1 when RE missing" "1" "$rc2"
rm -rf "$tmp"

exit $fail
