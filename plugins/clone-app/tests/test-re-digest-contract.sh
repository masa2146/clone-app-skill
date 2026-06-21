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

exit $fail
