#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SKILL="$ROOT/plugins/market-research/skills/market-research/SKILL.md"
fail=0
has() { grep -q "$1" "$SKILL" && echo "PASS contains: $1" || { echo "FAIL missing: $1"; fail=1; }; }

[[ -f "$SKILL" ]] || { echo "FAIL: SKILL.md missing"; exit 1; }
# frontmatter
has "description:"
has "trigger:"
# all six phases
has "Phase 0"
has "Phase 1"
has "Phase 2"
has "Phase 3"
has "Phase 4"
has "Phase 5"
# wires both scripts and the rubrics
has "fetch-charts.py"
has "history.py"
has "scoring-guide.md"
has "research-angles.md"
has "report-template.md"
# state contract + handoff
has "work/market-research"
has "history.json"
has "clone-app"
exit $fail
