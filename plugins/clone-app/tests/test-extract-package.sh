#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/extract-package.sh"
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "PASS: $desc"
  else
    echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1
  fi
}

check "full url" "com.example.app" \
  "$(bash "$SCRIPT" 'https://play.google.com/store/apps/details?id=com.example.app')"
check "url with extra params" "com.whatsapp" \
  "$(bash "$SCRIPT" 'https://play.google.com/store/apps/details?id=com.whatsapp&hl=en&gl=US')"
check "bare package passthrough" "com.spotify.music" \
  "$(bash "$SCRIPT" 'com.spotify.music')"

# invalid input → exit 1, empty stdout
out="$(bash "$SCRIPT" 'not a url' 2>/dev/null)"; rc=$?
check "invalid exit code" "1" "$rc"
check "invalid empty stdout" "" "$out"

exit $fail
