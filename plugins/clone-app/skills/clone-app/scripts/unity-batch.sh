#!/usr/bin/env bash
# Run one Unity batch step of the rebuild/verify chain, safely from any shell.
#
#   unity-batch.sh <project> <log> <Class.Method> [-cloneX value ...] [--gpu]
#
# Arguments go through as an array: zsh does not word-split "$ARGS", so a
# hand-built command line silently passed one glued argument (a test session
# lost two runs to it). --gpu drops -nographics, which rendering needs. Prints
# the step's own [Import…]/[Verify…]/[Render…] lines and compile errors, and
# exits with Unity's code. UNITY overrides the editor; default: newest in Hub.
set -uo pipefail
if [[ $# -lt 3 ]]; then
  echo "usage: unity-batch.sh <project> <log> <Class.Method> [args...] [--gpu]" >&2; exit 2
fi
UNITY="${UNITY:-$(ls -d /Applications/Unity/Hub/Editor/*/Unity.app/Contents/MacOS/Unity 2>/dev/null | sort -V | tail -1)}"
[[ -x "$UNITY" ]] || { echo "ERROR: no Unity editor (set UNITY=...)" >&2; exit 2; }
proj=$1 log=$2 method=$3; shift 3
gfx=(-nographics); args=()
for a in "$@"; do if [[ $a == --gpu ]]; then gfx=(); else args+=("$a"); fi; done
"$UNITY" -batchmode "${gfx[@]}" -projectPath "$proj" -executeMethod "$method" ${args[@]+"${args[@]}"} -logFile "$log"
code=$?
grep -E '^\[(ImportExtracted|VerifyImport|RenderLayout|ImportUI)\]|error CS|threw exception' "$log" | head -40
exit $code
