#!/usr/bin/env bash
set -euo pipefail

# Download an APK/XAPK for a package by its Android package name.
#
# Source: APKCombo. The historical APKPure endpoint
# (d.apkpure.com/b/APK/<pkg>?version=latest) is now behind a Cloudflare
# bot challenge and returns HTTP 403 "Just a moment..." for every package,
# so a plain curl can no longer use it.
#
# APKCombo serves the real artifact in two steps, both reachable with a
# normal browser User-Agent and no JavaScript:
#   1. GET https://apkcombo.com/app/<pkg>/download/apk  -> an HTML page that
#      embeds the signed download as a relative  /r2?u=<url-encoded-signed-url>
#      link (the URL slug segment is ignored by the server, so a fixed "app"
#      works for any package).
#   2. GET https://apkcombo.com<that /r2 path>  -> the apk/xapk bytes.
#
# CLONE_APP_CURL overrides the curl binary (used by the tests to inject a stub).

package="${1:-}"
out_dir="${2:-}"
curl_bin="${CLONE_APP_CURL:-curl}"

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
REFERER="https://apkcombo.com/"
page_url="https://apkcombo.com/app/${package}/download/apk"

if [[ -z "$package" || -z "$out_dir" ]]; then
  echo "ERROR: usage: download-apk.sh <package> <out-dir>" >&2
  exit 1
fi

mkdir -p "$out_dir"
page_file="$out_dir/download-page.html"
tmp_file="$out_dir/app.download"

# --- Step 1: fetch the download page and extract the signed /r2 link ---------
r2_path=""
for attempt in 1 2 3; do
  if "$curl_bin" -sL -A "$UA" -H "Referer: $REFERER" "$page_url" --output "$page_file" 2>/dev/null; then
    r2_path="$(grep -oE '/r2\?u=[^"]*' "$page_file" | head -1 || true)"
    [[ -n "$r2_path" ]] && break
  fi
  echo "download-page attempt $attempt failed (or no link yet), retrying..." >&2
  sleep 1
done
rm -f "$page_file"

if [[ -z "$r2_path" ]]; then
  echo "ERROR: no download link found for '$package' on APKCombo ($page_url)." >&2
  echo "       The app may not be available there, or the page format changed." >&2
  exit 1
fi

# Links in the HTML use raw '&'; decode '&amp;' defensively in case that changes.
r2_path="${r2_path//&amp;/&}"
artifact_url="https://apkcombo.com${r2_path}"

# --- Step 2: download the actual artifact ------------------------------------
ok=0
for attempt in 1 2 3; do
  if "$curl_bin" -sL --fail -A "$UA" -H "Referer: $REFERER" "$artifact_url" --output "$tmp_file" 2>/dev/null; then
    ok=1; break
  fi
  echo "artifact download attempt $attempt failed, retrying..." >&2
  sleep 1
done

if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: failed to download $package artifact after 3 attempts." >&2
  rm -f "$tmp_file"
  exit 1
fi

# Decide extension: both APK and XAPK are ZIPs. XAPK = a zip bundle containing
# manifest.json plus at least one split .apk entry; a plain APK has neither.
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
