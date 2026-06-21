#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="$HERE/.."   # plugins/clone-app
CONTRACT="$P/skills/clone-app/references/re-digest-contract.md"
DIGEST_FIX="$HERE/fixtures/re-digest.sample.md"
PAYLOAD_FIX="$HERE/fixtures/payloads.sample.json"
fail=0
has() { grep -qF "$2" "$1" && echo "PASS: $3" || { echo "FAIL: $3 — '$2' not in ${1##*/}"; fail=1; }; }

# Contract doc exists and documents every required re-digest.md section heading
for sec in "## Framework & Stack" "## Hosts" "## Endpoint Inventory" \
           "## Key Flow Payloads" "## BuildConfig Secrets" "## Feature Signals" "## RE Method"; do
  has "$CONTRACT" "$sec" "contract documents section $sec"
done

# Contract doc documents every required payloads.json key
for key in '"package"' '"re_method"' '"endpoints"' '"buildconfig"' \
           '"request_body"' '"response"' '"headers"'; do
  has "$CONTRACT" "$key" "contract documents json key $key"
done

# Contract names the three output files and the three RE Method values
for tok in "re-digest.md" "payloads.json" "re-summary.txt" \
           "re-skill" "direct-scripts" "limited:"; do
  has "$CONTRACT" "$tok" "contract names token $tok"
done

# Digest fixture has every required section heading
for sec in "## Framework & Stack" "## Hosts" "## Endpoint Inventory" \
           "## Key Flow Payloads" "## BuildConfig Secrets" "## Feature Signals" "## RE Method"; do
  has "$DIGEST_FIX" "$sec" "digest fixture has section $sec"
done

# Payload fixture is valid JSON and has the required shape
python3 -c "
import json,sys
d=json.load(open('$PAYLOAD_FIX'))
for k in ('package','re_method','endpoints','buildconfig'):
    assert k in d, 'missing top key '+k
assert isinstance(d['endpoints'],list) and d['endpoints'], 'endpoints must be non-empty list'
for e in d['endpoints']:
    for k in ('host','method','path','auth','source','request_body','response','headers'):
        assert k in e, 'endpoint missing key '+k
print('PASS: payload fixture shape valid')
" || { echo "FAIL: payload fixture shape"; fail=1; }

# --- SKILL.md Phase 2 wiring (Task 2) ---
SKILL="$P/skills/clone-app/SKILL.md"
hasS() { grep -qF "$1" "$SKILL" && echo "PASS: SKILL $2" || { echo "FAIL: SKILL $2 — '$1' missing"; fail=1; }; }
hasReS() { grep -qE "$1" "$SKILL" && echo "PASS: SKILL $2" || { echo "FAIL: SKILL $2 — /$1/ missing"; fail=1; }; }

hasS "re-digest-contract.md" "Phase 2 points at the digest contract"
hasReS "subagent|Agent tool|dispatch" "Phase 2 dispatches a subagent"
hasS "android-reverse-engineering skill" "Phase 2 names the RE skill branch"
hasS "direct-scripts" "Phase 2 names the script-fallback branch"
hasS "re-summary.txt" "Phase 2c consumes the summary"
hasS "payloads.json" "Phase 5 consumes payloads.json"
hasS "Backend API Surface" "Phase 6 adds the Backend API Surface section"
hasS "RE subagent" "error table covers subagent failure"

exit $fail
