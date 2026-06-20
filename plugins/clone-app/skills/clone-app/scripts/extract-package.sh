#!/usr/bin/env bash
set -euo pipefail

input="${1:-}"
if [[ -z "$input" ]]; then
  echo "ERROR: usage: extract-package.sh <play-url-or-package>" >&2
  exit 1
fi

# Case 1: full URL containing id=<package>
if [[ "$input" =~ id=([a-zA-Z0-9._]+) ]]; then
  echo "${BASH_REMATCH[1]}"
  exit 0
fi

# Case 2: already a bare package (must contain a dot, valid chars only)
if [[ "$input" =~ ^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$ ]]; then
  echo "$input"
  exit 0
fi

echo "ERROR: could not extract package from '$input'" >&2
exit 1
