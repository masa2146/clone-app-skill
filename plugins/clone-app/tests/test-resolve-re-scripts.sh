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

# When the sibling is absent but the RE plugin lives in the Claude plugin cache
# (the real install layout: cache/<marketplace>/android-reverse-engineering/<version>/...),
# the resolver discovers it there. Point both env vars at temp dirs: the cache
# var at a fake versioned layout, the root at a dir with no sibling.
tmp="$(mktemp -d)"
fake="$tmp/cache/some-marketplace/android-reverse-engineering/9.9.9/skills/android-reverse-engineering/scripts"
mkdir -p "$fake"; : > "$fake/decompile.sh"
out2="$(CLAUDE_PLUGIN_ROOT="$tmp/clone-app" CLAUDE_PLUGIN_CACHE="$tmp/cache" bash "$SCRIPT" 2>/dev/null)"; rc2=$?
check "exit 0 when RE only in cache" "0" "$rc2"
check "resolves the cached scripts dir" "$fake" "$out2"

# When neither a sibling nor any cache entry exists → exit 1
out3="$(CLAUDE_PLUGIN_ROOT="$tmp/clone-app" CLAUDE_PLUGIN_CACHE="$tmp/empty" bash "$SCRIPT" 2>/dev/null)"; rc3=$?
check "exit 1 when RE missing everywhere" "1" "$rc3"
rm -rf "$tmp"

exit $fail
