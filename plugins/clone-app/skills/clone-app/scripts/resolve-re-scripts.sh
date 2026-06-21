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

# Locate the RE plugin's scripts dir. The tail is always
# .../android-reverse-engineering/skills/android-reverse-engineering/scripts,
# but the parent layout differs by install:
#   - repo / dev checkout:  plugins/android-reverse-engineering/skills/...   (flat sibling)
#   - plugin cache:         cache/<marketplace>/android-reverse-engineering/<version>/skills/...
# so we probe a list of candidate globs and take the first match (highest
# version when several exist).
tail="skills/android-reverse-engineering/scripts"
# `|| true`: under `set -e`, a bare `var=$(cmd)` whose cmd fails (e.g. the dir
# doesn't exist) aborts the script. We want to fall through to the cache globs.
parent="$(cd "$plugin_root/.." 2>/dev/null && pwd || true)"

candidates=()
# 1. flat sibling next to clone-app (repo/dev layout)
[[ -n "$parent" ]] && candidates+=("$parent/android-reverse-engineering/$tail")
# 2. versioned sibling under the same marketplace dir (cache layout)
[[ -n "$parent" ]] && candidates+=("$parent"/android-reverse-engineering/*/"$tail")
# 3. anywhere under the Claude plugin cache (any marketplace, any version)
cache_root="${CLAUDE_PLUGIN_CACHE:-$HOME/.claude/plugins/cache}"
candidates+=("$cache_root"/*/android-reverse-engineering/*/"$tail")
candidates+=("$cache_root"/*/android-reverse-engineering/"$tail")

re_scripts=""
for cand in "${candidates[@]}"; do
  # glob entries that didn't match stay literal (with '*'); skip those.
  [[ "$cand" == *"*"* ]] && continue
  [[ -d "$cand" ]] || continue
  # Prefer the highest version: keep the lexically-greatest matching path.
  if [[ -z "$re_scripts" || "$cand" > "$re_scripts" ]]; then
    re_scripts="$cand"
  fi
done

if [[ -z "$re_scripts" || ! -d "$re_scripts" ]]; then
  echo "ERROR: android-reverse-engineering scripts not found. Looked for:" >&2
  echo "  - $parent/android-reverse-engineering/$tail (sibling)" >&2
  echo "  - $cache_root/*/android-reverse-engineering/*/$tail (cache)" >&2
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
