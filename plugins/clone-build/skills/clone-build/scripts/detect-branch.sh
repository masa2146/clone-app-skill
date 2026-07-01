#!/usr/bin/env bash
# Classify a clone-build-spec.md as game|app + substack from its "Selected stack" line.
# Reads ONLY that line — the spec template always carries a "Game variant (Unity)"
# section, so whole-file scanning would false-positive every app as a game.
set -uo pipefail

SPEC="${1:-}"
if [[ -z "$SPEC" || ! -f "$SPEC" ]]; then
  echo "ERROR: usage: detect-branch.sh <clone-build-spec.md>" >&2
  exit 2
fi

line="$(grep -i 'selected stack' "$SPEC" | head -n1 | tr 'A-Z' 'a-z')"
if [[ -z "$line" ]]; then
  echo "ERROR: no 'Selected stack' line in $SPEC" >&2
  exit 3
fi

branch=app; substack=unknown
case "$line" in
  *unity*|*il2cpp*)            branch=game; substack=unity ;;
  *flutter*)                   substack=flutter ;;
  *react*native*)              substack=react-native ;;
  *native*|*kotlin*|*compose*|*jetpack*) substack=native-android ;;
esac

echo "$branch $substack"
