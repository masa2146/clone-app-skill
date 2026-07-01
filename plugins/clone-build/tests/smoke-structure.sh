#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # repo root
P="$ROOT/plugins/clone-build"
fail=0
must_exist() { [[ -e "$1" ]] && echo "PASS exists: ${1#$ROOT/}" || { echo "FAIL missing: ${1#$ROOT/}"; fail=1; }; }
must_exec()  { [[ -x "$1" ]] && echo "PASS exec: ${1#$ROOT/}"   || { echo "FAIL not exec: ${1#$ROOT/}"; fail=1; }; }

must_exist "$P/.claude-plugin/plugin.json"
must_exist "$P/skills/clone-build/SKILL.md"
must_exist "$P/commands/clone-build.md"
must_exist "$P/README.md"

for s in detect-branch.sh preflight.sh run-gate.sh; do
  must_exist "$P/skills/clone-build/scripts/$s"; must_exec "$P/skills/clone-build/scripts/$s"
done
must_exist "$P/skills/clone-build/scripts/gen-build-plan.py"
for r in plan-contract gate-catalog build-report-template; do
  must_exist "$P/skills/clone-build/references/$r.md"
done

# JSON validity
python3 -c "import json;json.load(open('$P/.claude-plugin/plugin.json'));json.load(open('$ROOT/.claude-plugin/marketplace.json'))" \
  && echo "PASS json valid" || { echo "FAIL json invalid"; fail=1; }

# clone-build present in marketplace
python3 -c "
import json;d=json.load(open('$ROOT/.claude-plugin/marketplace.json'))
names=[p['name'] for p in d['plugins']]
assert 'clone-build' in names, names
print('PASS marketplace has clone-build')" || { echo "FAIL marketplace entry"; fail=1; }

# upstream untouched guard
if [[ -n "$(git -C "$ROOT" status --porcelain plugins/android-reverse-engineering/ 2>/dev/null)" ]]; then
  echo "FAIL upstream tree modified"; fail=1
else
  echo "PASS upstream untouched"
fi

exit $fail
