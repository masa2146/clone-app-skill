#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # repo root
P="$ROOT/plugins/market-research"
fail=0
must_exist() { [[ -e "$1" ]] && echo "PASS exists: ${1#$ROOT/}" || { echo "FAIL missing: ${1#$ROOT/}"; fail=1; }; }
must_exec()  { [[ -x "$1" ]] && echo "PASS exec: ${1#$ROOT/}"   || { echo "FAIL not exec: ${1#$ROOT/}"; fail=1; }; }

must_exist "$P/.claude-plugin/plugin.json"
must_exist "$P/commands/market-research.md"
must_exist "$P/README.md"
must_exist "$P/skills/market-research/SKILL.md"
for s in fetch-charts.py history.py fetch-play-charts.py play.py trends.py; do
  must_exist "$P/skills/market-research/scripts/$s"
  must_exec  "$P/skills/market-research/scripts/$s"
done
for r in research-angles scoring-guide report-template numeric-sources; do
  must_exist "$P/skills/market-research/references/$r.md"
done

# JSON validity: plugin manifest + marketplace
python3 -c "import json;json.load(open('$P/.claude-plugin/plugin.json'));json.load(open('$ROOT/.claude-plugin/marketplace.json'))" \
  && echo "PASS json valid" || { echo "FAIL json invalid"; fail=1; }

# all three plugins present in marketplace
python3 -c "
import json;d=json.load(open('$ROOT/.claude-plugin/marketplace.json'))
names=[p['name'] for p in d['plugins']]
assert 'market-research' in names and 'clone-app' in names and 'android-reverse-engineering' in names
print('PASS marketplace has all three plugins')" || { echo "FAIL marketplace entries"; fail=1; }

exit $fail
