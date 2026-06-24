#!/usr/bin/env bash
# Classify an APK/XAPK as a Unity build: il2cpp | mono | none.
set -uo pipefail

APK="${1:-}"
if [[ -z "$APK" || ! -f "$APK" ]]; then
  echo "ERROR: usage: detect-unity.sh <apk-or-xapk>" >&2
  exit 2
fi

listing="$(unzip -Z1 "$APK" 2>/dev/null)" || {
  echo "ERROR: cannot read zip: $APK" >&2; exit 2; }

if grep -q 'global-metadata\.dat' <<<"$listing" \
   && grep -qi 'libil2cpp\.so' <<<"$listing"; then
  echo il2cpp; exit 0
fi
if grep -Eq 'assets/bin/Data/Managed/.*\.dll' <<<"$listing"; then
  echo mono; exit 0
fi
echo none
exit 0
