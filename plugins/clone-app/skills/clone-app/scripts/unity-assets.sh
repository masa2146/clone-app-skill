#!/usr/bin/env bash
# Extract Unity game assets (textures, sprites, audio, scenes, prefabs) from an
# APK via AssetRipper's CLI. Only the tool-missing path is exercised by tests.
set -uo pipefail

APK="${1:-}"; OUT="${2:-}"
if [[ -z "$APK" || -z "$OUT" ]]; then
  echo "ERROR: usage: unity-assets.sh <apk> <out-dir>" >&2
  exit 2
fi

BIN="${ASSETRIPPER_CLI:-AssetRipper}"
if ! command -v "$BIN" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: AssetRipper CLI not found.
Install it (needs the .NET runtime): https://github.com/AssetRipper/AssetRipper
Put the CLI on PATH, or set ASSETRIPPER_CLI=/path/to/AssetRipper.
EOF
  exit 3
fi

mkdir -p "$OUT"
"$BIN" "$APK" -o "$OUT"
