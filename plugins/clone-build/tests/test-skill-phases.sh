#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-build/SKILL.md"
fail=0
need() { if grep -qF "$1" "$S"; then echo "PASS: SKILL has '$1'"; else echo "FAIL: SKILL missing '$1'"; fail=1; fi; }

for p in "## P0" "## P1" "## P2" "## P3" "## P4" "## P5"; do need "$p"; done
need "detect-branch.sh"
need "preflight.sh"
need "gen-build-plan.py"
need "run-gate.sh"
need "game-build-guide.md"
need "app-build-guide.md"
need "plan-contract.md"
need "gate-catalog.md"
need "subagent-driven-development"

exit $fail
