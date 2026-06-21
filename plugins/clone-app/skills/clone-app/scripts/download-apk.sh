#!/usr/bin/env bash
set -euo pipefail

# Download an APK/XAPK for a package by its Android package name.
#
# Source: apkeep (https://github.com/EFForg/apkeep), default download source
# apk-pure. apkeep is a maintained Rust CLI that handles the mirror's HTML,
# Cloudflare User-Agent dance, retries, and split-APK (XAPK) bundling for us —
# no auth, no JavaScript, no per-mirror scraping to maintain. Install with
# `brew install apkeep` (or `cargo install apkeep`).
#
# apkeep writes "<package>.apk" or "<package>.xapk" into the output dir; we
# rename it to "app.<ext>" so the rest of the skill sees a stable path.
#
# CLONE_APP_APKEEP overrides the apkeep binary (used by the tests to inject a
# stub). CLONE_APP_APKEEP_SOURCE overrides the download source (default apk-pure).

package="${1:-}"
out_dir="${2:-}"
apkeep_bin="${CLONE_APP_APKEEP:-apkeep}"
source="${CLONE_APP_APKEEP_SOURCE:-apk-pure}"

if [[ -z "$package" || -z "$out_dir" ]]; then
  echo "ERROR: usage: download-apk.sh <package> <out-dir>" >&2
  exit 1
fi

if ! command -v "$apkeep_bin" >/dev/null 2>&1; then
  echo "ERROR: apkeep not found. Install it with 'brew install apkeep'" >&2
  echo "       (or 'cargo install apkeep'), then re-run." >&2
  exit 1
fi

mkdir -p "$out_dir"

# apkeep handles its own retries; run it once and check the result.
if ! "$apkeep_bin" -a "$package" -d "$source" "$out_dir" >&2; then
  echo "ERROR: apkeep failed to download '$package' from $source." >&2
  echo "       The app may not be available there; try another -d source." >&2
  exit 1
fi

# apkeep names the artifact after the package; find whichever it produced.
artifact=""
for cand in "$out_dir/$package.xapk" "$out_dir/$package.apk"; do
  [[ -f "$cand" ]] && { artifact="$cand"; break; }
done

if [[ -z "$artifact" ]]; then
  echo "ERROR: apkeep reported success but no artifact found in $out_dir." >&2
  exit 1
fi

ext="${artifact##*.}"
final="$out_dir/app.$ext"
mv -f "$artifact" "$final"
echo "$final"
