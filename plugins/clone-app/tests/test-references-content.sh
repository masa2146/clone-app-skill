#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
R="$HERE/../skills/clone-app/references"
fail=0
has() { # file substring
  if grep -qF "$2" "$1" 2>/dev/null; then echo "PASS: $(basename "$1") has '$2'"
  else echo "FAIL: $(basename "$1") missing '$2'"; fail=1; fi
}

has "$R/design-capture-guide.md" "design-tokens.json"
has "$R/design-capture-guide.md" "confidence"
has "$R/design-capture-guide.md" "screenshots"
has "$R/unity-re-guide.md" "Il2CppInspectorRedux"
has "$R/unity-re-guide.md" "AssetRipper"
has "$R/unity-re-guide.md" "ilspycmd"
has "$R/clone-build-spec-template.md" "Screen-by-screen"
has "$R/clone-build-spec-template.md" "Acceptance criteria"
has "$R/clone-build-spec-template.md" "Game variant"
has "$R/re-digest-contract.md" "design-tokens.json"
has "$R/re-digest-contract.md" "unity-digest.md"
has "$R/report-template.md" "Design System"
has "$R/report-template.md" "Game Assets"

exit $fail
