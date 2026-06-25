#!/usr/bin/env bash
# Recover the C# type model from a Unity IL2CPP build via Il2CppInspectorRedux.
# Flags follow the Il2CppInspector CLI; adjust to your installed CLI version if
# they differ. Only the tool-missing path is exercised by tests.
set -uo pipefail

SO="${1:-}"; META="${2:-}"; OUT="${3:-}"
if [[ -z "$SO" || -z "$META" || -z "$OUT" ]]; then
  echo "ERROR: usage: il2cpp-dump.sh <libil2cpp.so> <global-metadata.dat> <out-dir>" >&2
  exit 2
fi

BIN="${IL2CPP_INSPECTOR_CLI:-Il2CppInspector}"
if ! command -v "$BIN" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: Il2CppInspectorRedux CLI not found.
Install it (needs the .NET SDK): https://github.com/LukeFZ/Il2CppInspectorRedux
Build the CLI, put it on PATH, or set IL2CPP_INSPECTOR_CLI=/path/to/cli.
EOF
  exit 3
fi

mkdir -p "$OUT"
# Produce C# stub headers + a metadata JSON describing types/methods/fields.
"$BIN" --bin "$SO" --metadata "$META" \
       --select-outputs --cs-out "$OUT/types.cs" --json-out "$OUT/metadata.json"
