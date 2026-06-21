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

# The RE scripts (fingerprint.sh, find-api-calls.sh) use bash 4+ syntax such as
# ${VAR,,}. macOS ships bash 3.2, where those fail with "bad substitution".
# SKILL.md invokes the RE scripts as `bash "$RE/..."`, so the version that
# matters is whatever `bash` resolves to on PATH — warn (not fatal: the path
# still resolves, and a caller may have a newer bash elsewhere) so the user
# gets an actionable message instead of a cryptic substitution error.
re_bash_major="$(bash -c 'echo "${BASH_VERSINFO[0]:-0}"' 2>/dev/null || echo 0)"
if [[ "$re_bash_major" -lt 4 ]]; then
  echo "WARNING: 'bash' on PATH is version ${re_bash_major}.x; the reverse-engineering" >&2
  echo "         scripts need bash 4+ (they use \${VAR,,} etc.) and will fail otherwise." >&2
  echo "         Install a modern bash, e.g.: brew install bash" >&2
fi

echo "$re_scripts"
