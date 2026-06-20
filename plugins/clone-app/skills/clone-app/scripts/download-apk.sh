#!/usr/bin/env bash
set -euo pipefail

package="${1:-}"
out_dir="${2:-}"
curl_bin="${CLONE_APP_CURL:-curl}"

if [[ -z "$package" || -z "$out_dir" ]]; then
  echo "ERROR: usage: download-apk.sh <package> <out-dir>" >&2
  exit 1
fi

mkdir -p "$out_dir"
tmp_file="$out_dir/app.download"
url="https://d.apkpure.com/b/APK/${package}?version=latest"

ok=0
for attempt in 1 2 3; do
  if "$curl_bin" -L --fail "$url" --output "$tmp_file" 2>/dev/null; then
    ok=1; break
  fi
  echo "download attempt $attempt failed, retrying..." >&2
  sleep 1
done

if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: failed to download $package after 3 attempts from $url" >&2
  rm -f "$tmp_file"
  exit 1
fi

# Decide extension: both APK and XAPK are ZIPs. XAPK = zip containing manifest.json + >=2 .apk entries.
ext="apk"
if entries="$(unzip -Z1 "$tmp_file" 2>/dev/null)"; then
  apk_count="$(grep -c '\.apk$' <<<"$entries" || true)"
  if grep -q '^manifest\.json$' <<<"$entries" && [[ "$apk_count" -ge 1 ]]; then
    ext="xapk"
  fi
fi

final="$out_dir/app.$ext"
mv "$tmp_file" "$final"
echo "$final"
