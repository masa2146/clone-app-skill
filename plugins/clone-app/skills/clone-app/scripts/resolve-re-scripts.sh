#!/usr/bin/env bash
set -euo pipefail

# Determine this plugin's root. Prefer the env var Claude Code sets; fall back
# to deriving from this script's own location (…/clone-app/skills/clone-app/scripts).
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
  plugin_root="$CLAUDE_PLUGIN_ROOT"
else
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # scripts -> clone-app -> skills -> clone-app(plugin root)
  plugin_root="$(cd "$script_dir/../../.." && pwd)"
fi

# Sibling RE plugin lives next to clone-app under plugins/
re_scripts="$(cd "$plugin_root/.." 2>/dev/null && pwd)/android-reverse-engineering/skills/android-reverse-engineering/scripts"

if [[ ! -d "$re_scripts" ]]; then
  echo "ERROR: android-reverse-engineering scripts not found at: $re_scripts" >&2
  echo "Install it: /plugin install android-reverse-engineering@android-reverse-engineering-skill" >&2
  exit 1
fi

echo "$re_scripts"
