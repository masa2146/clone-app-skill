#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
R="$HERE/../skills/clone-build/references"
fail=0
need() { local f="$1" pat="$2"; if grep -qiF "$pat" "$f"; then echo "PASS: $(basename "$f") has '$pat'"; else echo "FAIL: $(basename "$f") missing '$pat'"; fail=1; fi; }

for kw in "depends_on" "needs-human-input" "forcing rule" "pass_when" "gate"; do
  need "$R/plan-contract.md" "$kw"
done
for kw in "visual-diff" "launch-crash" "build" "tdd"; do
  need "$R/gate-catalog.md" "$kw"
done
for kw in "SKIP" "gate" "visual-diff"; do
  need "$R/build-report-template.md" "$kw"
done

exit $fail
