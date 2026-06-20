# Clone App Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/clone-app` Claude Code skill that downloads an Android app's APK from a Google Play URL, reverse engineers it (via the existing `android-reverse-engineering` plugin), analyzes store presence, estimates AI-assisted clone effort + infra cost, produces a market-viability report, and optionally hands off to `writing-plans`.

**Architecture:** A new `clone-app` plugin living **inside the fork** of `masa2146/android-reverse-engineering-skill`, alongside the untouched upstream `android-reverse-engineering` plugin. The orchestrator `SKILL.md` drives 8 phases (0–7); deterministic steps (URL parsing, APK download, store scrape, package-name extraction) are factored into small standalone bash/python helper scripts that are unit-testable. The RE plugin's existing scripts are invoked directly by path. AI-judgment phases (stack recommendation, effort estimate, viability verdict) live as prose instructions + reference templates in the skill.

**Tech Stack:** Bash (helper scripts + glue), Python 3 (store scrape + JSON parsing where bash is too brittle), Markdown (skill/command/reference docs), `bats` or plain bash assertions for script tests, `curl`, the upstream RE scripts (jadx/Java).

## Global Constraints

- Repo root: `/Users/fatih.bulut/PythonWorks/clone_app_skill` (the cloned fork).
- Upstream plugin dir `plugins/android-reverse-engineering/` is **NEVER modified** — zero edits, to keep `git pull upstream master` conflict-free.
- New plugin dir: `plugins/clone-app/`.
- RE scripts are referenced via `${CLAUDE_PLUGIN_ROOT}` of the clone-app plugin, resolving sibling: `"$(dirname "$CLAUDE_PLUGIN_ROOT")/android-reverse-engineering/skills/android-reverse-engineering/scripts"`.
- All skill `${CLAUDE_PLUGIN_ROOT}` references use that exact env var (Claude Code sets it per-plugin).
- Working dir for runtime artifacts: `./work/{package}/` (relative to user's cwd, NOT inside the plugin).
- Package name regex (verbatim): `id=([a-zA-Z0-9._]+)`
- APKPure download URL (verbatim): `https://d.apkpure.com/b/APK/{PACKAGE}?version=latest`
- "AI Sprint" = one focused Claude Code session (~2-4 hours human review time). Use this unit everywhere; never calendar time.
- Bash scripts: `set -euo pipefail` at top, `#!/usr/bin/env bash` shebang.
- Python scripts: `#!/usr/bin/env python3`, stdlib only (no pip installs) — use `urllib`, `json`, `re`, `html.parser`.
- Report filename (verbatim): `clone-report-YYYY-MM-DD.md` where date is the run date.

---

## File Structure

**Plugin scaffold:**
- `plugins/clone-app/.claude-plugin/plugin.json` — plugin manifest
- `.claude-plugin/marketplace.json` — MODIFY: add clone-app entry (this is the only root-level shared file we touch; low conflict risk)
- `plugins/clone-app/skills/clone-app/SKILL.md` — orchestrator, all 8 phases
- `plugins/clone-app/commands/clone-app.md` — `/clone-app` slash command

**Helper scripts (deterministic, testable):**
- `plugins/clone-app/skills/clone-app/scripts/extract-package.sh` — Google Play URL → package name
- `plugins/clone-app/skills/clone-app/scripts/download-apk.sh` — APKPure download w/ retries + filetype detect
- `plugins/clone-app/skills/clone-app/scripts/resolve-re-scripts.sh` — locate sibling RE scripts dir, fail loud if absent
- `plugins/clone-app/skills/clone-app/scripts/scrape-play-store.py` — Google Play page → metrics JSON
- `plugins/clone-app/skills/clone-app/scripts/check-appstore.py` — iTunes Search API → iOS presence JSON

**Reference docs (AI-judgment guidance):**
- `plugins/clone-app/skills/clone-app/references/effort-estimation-guide.md` — how to build the AI-sprint table
- `plugins/clone-app/skills/clone-app/references/infra-cost-guide.md` — hosting/db/CDN cost heuristics
- `plugins/clone-app/skills/clone-app/references/report-template.md` — the clone-report skeleton
- `plugins/clone-app/skills/clone-app/references/stack-recommendation-guide.md` — how to pick/present 2-3 stacks

**Tests:**
- `plugins/clone-app/tests/test-extract-package.sh`
- `plugins/clone-app/tests/test-download-apk.sh`
- `plugins/clone-app/tests/test-resolve-re-scripts.sh`
- `plugins/clone-app/tests/test-scrape-play-store.py`
- `plugins/clone-app/tests/test-check-appstore.py`
- `plugins/clone-app/tests/fixtures/` — sample HTML/JSON fixtures
- `plugins/clone-app/tests/run-all.sh` — runs every test

**Docs:**
- `plugins/clone-app/README.md` — install + usage

---

## Task 1: Repo bootstrap + plugin scaffold

**Files:**
- Verify: `/Users/fatih.bulut/PythonWorks/clone_app_skill/` is the cloned fork with `plugins/android-reverse-engineering/` present
- Create: `plugins/clone-app/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json` (add clone-app plugin entry)

**Interfaces:**
- Produces: a valid plugin discoverable by `/plugin install clone-app@android-reverse-engineering-skill`. Plugin name string: `clone-app`. Marketplace name string stays: `android-reverse-engineering-skill`.

- [ ] **Step 1: Verify the working dir is the cloned fork**

Run:
```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  ls plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/decompile.sh && \
  git remote -v
```
Expected: the `decompile.sh` path lists successfully, and `git remote -v` shows an `origin` pointing at `masa2146/android-reverse-engineering-skill`.

If the directory is empty (fork not cloned yet), run:
```bash
cd /Users/fatih.bulut/PythonWorks && \
  rm -rf clone_app_skill && \
  git clone https://github.com/masa2146/android-reverse-engineering-skill.git clone_app_skill && \
  cd clone_app_skill && \
  git remote add upstream https://github.com/SimoneAvogadro/android-reverse-engineering-skill.git
```
Expected: clone succeeds, upstream remote added. Re-run the verify command above.

- [ ] **Step 2: Create the plugin manifest**

Create `plugins/clone-app/.claude-plugin/plugin.json`:
```json
{
  "name": "clone-app",
  "version": "0.1.0",
  "description": "Analyze a Google Play app: download APK, reverse engineer it, estimate AI-assisted clone effort and infra cost, assess market viability, and optionally generate an implementation plan.",
  "author": {
    "name": "masa2146"
  },
  "repository": "https://github.com/masa2146/android-reverse-engineering-skill",
  "license": "Apache-2.0",
  "keywords": ["android", "clone", "feasibility", "effort-estimation", "market-analysis", "reverse-engineering"],
  "skills": "./skills/",
  "commands": "./commands/"
}
```

- [ ] **Step 3: Add clone-app to the marketplace catalog**

Read the current `.claude-plugin/marketplace.json`, then append a second object to the `plugins` array (keep the existing `android-reverse-engineering` entry untouched). The `plugins` array becomes:
```json
"plugins": [
  {
    "name": "android-reverse-engineering",
    "source": "./plugins/android-reverse-engineering",
    "description": "Decompile Android APK/JAR/AAR with jadx, trace call flows through libraries, and document extracted APIs.",
    "version": "1.5.0",
    "author": { "name": "Simone Avogadro" },
    "repository": "https://github.com/SimoneAvogadro/android-reverse-engineering-skill",
    "license": "Apache-2.0",
    "keywords": ["android", "reverse-engineering", "apk", "jadx", "decompile", "api-extraction"],
    "category": "security"
  },
  {
    "name": "clone-app",
    "source": "./plugins/clone-app",
    "description": "Analyze a Google Play app for cloning: APK reverse engineering, AI-assisted effort estimation, market viability.",
    "version": "0.1.0",
    "author": { "name": "masa2146" },
    "repository": "https://github.com/masa2146/android-reverse-engineering-skill",
    "license": "Apache-2.0",
    "keywords": ["android", "clone", "feasibility", "effort-estimation", "market-analysis"],
    "category": "security"
  }
]
```

- [ ] **Step 4: Validate JSON**

Run:
```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  python3 -c "import json; json.load(open('plugins/clone-app/.claude-plugin/plugin.json')); json.load(open('.claude-plugin/marketplace.json')); print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/.claude-plugin/plugin.json .claude-plugin/marketplace.json && \
  git commit -m "feat(clone-app): scaffold plugin manifest and marketplace entry"
```

---

## Task 2: `extract-package.sh` — Google Play URL → package name

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/extract-package.sh`
- Test: `plugins/clone-app/tests/test-extract-package.sh`

**Interfaces:**
- Produces: `extract-package.sh <url-or-package>` prints the bare package name to stdout, exit 0. On no match, prints nothing to stdout, writes `ERROR: could not extract package` to stderr, exit 1. Accepts either a full Play URL or an already-bare package name (passthrough if it matches `^[a-zA-Z0-9._]+$` with a dot).

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-extract-package.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/extract-package.sh"
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "PASS: $desc"
  else
    echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1
  fi
}

check "full url" "com.example.app" \
  "$(bash "$SCRIPT" 'https://play.google.com/store/apps/details?id=com.example.app')"
check "url with extra params" "com.whatsapp" \
  "$(bash "$SCRIPT" 'https://play.google.com/store/apps/details?id=com.whatsapp&hl=en&gl=US')"
check "bare package passthrough" "com.spotify.music" \
  "$(bash "$SCRIPT" 'com.spotify.music')"

# invalid input → exit 1, empty stdout
out="$(bash "$SCRIPT" 'not a url' 2>/dev/null)"; rc=$?
check "invalid exit code" "1" "$rc"
check "invalid empty stdout" "" "$out"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-extract-package.sh
```
Expected: FAIL (script does not exist yet — `bash: ...extract-package.sh: No such file or directory`).

- [ ] **Step 3: Write minimal implementation**

Create `plugins/clone-app/skills/clone-app/scripts/extract-package.sh`:
```bash
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
chmod +x /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/skills/clone-app/scripts/extract-package.sh && \
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-extract-package.sh
```
Expected: all `PASS`, exit 0.

- [ ] **Step 5: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/skills/clone-app/scripts/extract-package.sh plugins/clone-app/tests/test-extract-package.sh && \
  git commit -m "feat(clone-app): add extract-package.sh URL parser with tests"
```

---

## Task 3: `resolve-re-scripts.sh` — locate sibling RE scripts dir

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/resolve-re-scripts.sh`
- Test: `plugins/clone-app/tests/test-resolve-re-scripts.sh`

**Interfaces:**
- Consumes: env var `CLAUDE_PLUGIN_ROOT` (path to the clone-app plugin dir). Falls back to deriving its own location from `$0` if the env var is unset (so it works when run standalone in tests).
- Produces: `resolve-re-scripts.sh` prints the absolute path to the RE `scripts/` dir to stdout, exit 0. If that dir doesn't exist, writes a clear error naming the install command to stderr, exit 1.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-resolve-re-scripts.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/resolve-re-scripts.sh"
fail=0
check() { [[ "$2" == "$3" ]] && echo "PASS: $1" || { echo "FAIL: $1 — expected '$2' got '$3'"; fail=1; }; }

# In the real repo layout, the RE scripts dir exists as a sibling plugin.
out="$(bash "$SCRIPT" 2>/dev/null)"; rc=$?
check "exit 0 when RE present" "0" "$rc"
check "ends with scripts dir" "android-reverse-engineering/skills/android-reverse-engineering/scripts" \
  "$(basename "$(dirname "$(dirname "$(dirname "$out")")")")/$(basename "$(dirname "$(dirname "$out")")")/$(basename "$(dirname "$out")")/$(basename "$out")"
check "decompile.sh exists under resolved dir" "yes" \
  "$([[ -f "$out/decompile.sh" ]] && echo yes || echo no)"

# When CLAUDE_PLUGIN_ROOT points somewhere with no sibling RE plugin → exit 1
tmp="$(mktemp -d)"
out2="$(CLAUDE_PLUGIN_ROOT="$tmp/clone-app" bash "$SCRIPT" 2>/dev/null)"; rc2=$?
check "exit 1 when RE missing" "1" "$rc2"
rm -rf "$tmp"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-resolve-re-scripts.sh
```
Expected: FAIL (script missing).

- [ ] **Step 3: Write minimal implementation**

Create `plugins/clone-app/skills/clone-app/scripts/resolve-re-scripts.sh`:
```bash
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
chmod +x /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/skills/clone-app/scripts/resolve-re-scripts.sh && \
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-resolve-re-scripts.sh
```
Expected: all `PASS`, exit 0.

- [ ] **Step 5: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/skills/clone-app/scripts/resolve-re-scripts.sh plugins/clone-app/tests/test-resolve-re-scripts.sh && \
  git commit -m "feat(clone-app): add resolve-re-scripts.sh sibling-plugin locator with tests"
```

---

## Task 4: `download-apk.sh` — APKPure download with retries + filetype detect

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/download-apk.sh`
- Test: `plugins/clone-app/tests/test-download-apk.sh`

**Interfaces:**
- Consumes: `download-apk.sh <package> <out-dir>` and optional env `CLONE_APP_CURL` (override curl binary, used by test to inject a stub).
- Produces: downloads to `<out-dir>/app.<ext>` where ext is `xapk` or `apk` decided by magic bytes (ZIP `PK\x03\x04` for both; distinguish by presence of `manifest.json` + multiple `.apk` entries → xapk, else apk). Prints the final file path to stdout on success, exit 0. Retries up to 3 times on curl failure. On total failure: stderr message, exit 1.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-download-apk.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/download-apk.sh"
fail=0
check() { [[ "$2" == "$3" ]] && echo "PASS: $1" || { echo "FAIL: $1 — expected '$2' got '$3'"; fail=1; }; }

tmp="$(mktemp -d)"

# Stub curl: writes a minimal zip containing manifest.json + two apk entries → xapk
cat > "$tmp/fakecurl-xapk.sh" <<'EOF'
#!/usr/bin/env bash
out=""; prev=""
for a in "$@"; do [[ "$prev" == "--output" ]] && out="$a"; prev="$a"; done
workdir="$(mktemp -d)"
echo '{}' > "$workdir/manifest.json"
echo 'a' > "$workdir/base.apk"; echo 'b' > "$workdir/config.apk"
( cd "$workdir" && zip -q -r "$out" . )
exit 0
EOF
chmod +x "$tmp/fakecurl-xapk.sh"

path="$(CLONE_APP_CURL="$tmp/fakecurl-xapk.sh" bash "$SCRIPT" com.example.app "$tmp/out" 2>/dev/null)"; rc=$?
check "xapk exit 0" "0" "$rc"
check "xapk extension" "xapk" "${path##*.}"

# Stub curl that always fails → exit 1 after retries
cat > "$tmp/fakecurl-fail.sh" <<'EOF'
#!/usr/bin/env bash
exit 22
EOF
chmod +x "$tmp/fakecurl-fail.sh"
out2="$(CLONE_APP_CURL="$tmp/fakecurl-fail.sh" bash "$SCRIPT" com.example.app "$tmp/out2" 2>/dev/null)"; rc2=$?
check "fail exit 1" "1" "$rc2"

rm -rf "$tmp"
exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-download-apk.sh
```
Expected: FAIL (script missing).

- [ ] **Step 3: Write minimal implementation**

Create `plugins/clone-app/skills/clone-app/scripts/download-apk.sh`:
```bash
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
chmod +x /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/skills/clone-app/scripts/download-apk.sh && \
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-download-apk.sh
```
Expected: all `PASS`, exit 0. (Requires `zip`/`unzip` available — standard on macOS.)

- [ ] **Step 5: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/skills/clone-app/scripts/download-apk.sh plugins/clone-app/tests/test-download-apk.sh && \
  git commit -m "feat(clone-app): add download-apk.sh with retries and xapk/apk detection"
```

---

## Task 5: `scrape-play-store.py` — Google Play page → metrics JSON

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/scrape-play-store.py`
- Create: `plugins/clone-app/tests/fixtures/play-sample.html`
- Test: `plugins/clone-app/tests/test-scrape-play-store.py`

**Interfaces:**
- Consumes: `scrape-play-store.py <package>` fetches `https://play.google.com/store/apps/details?id=<package>&hl=en&gl=US`. For testing, `--html-file <path>` reads local HTML instead of network.
- Produces: prints a JSON object to stdout with keys: `package` (str), `title` (str|null), `rating` (float|null), `rating_count` (int|null), `installs` (str|null), `category` (str|null), `developer` (str|null), `updated` (str|null), `source` (str: "google-play"). Missing fields are `null`, never absent. Exit 0 even on partial extraction; exit 1 only on fetch error (network/HTTP) when not using `--html-file`.

- [ ] **Step 1: Create the test fixture**

Create `plugins/clone-app/tests/fixtures/play-sample.html` — a trimmed but realistic Play page. Include the data-bearing markup the scraper targets:
```html
<!DOCTYPE html>
<html><head><title>Example App - Apps on Google Play</title>
<script type="application/ld+json">
{"@type":"SoftwareApplication","name":"Example App","author":{"name":"Example Studio"},
"aggregateRating":{"ratingValue":"4.3","ratingCount":"12873"},
"applicationCategory":"GAME_PUZZLE"}
</script>
</head><body>
<div>Updated on<span>Jun 1, 2026</span></div>
<div>1,000,000+<span>Downloads</span></div>
</body></html>
```

- [ ] **Step 2: Write the failing test**

Create `plugins/clone-app/tests/test-scrape-play-store.py`:
```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "scrape-play-store.py")
FIXTURE = os.path.join(HERE, "fixtures", "play-sample.html")

def run():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "com.example.app", "--html-file", FIXTURE])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    check("package", d["package"] == "com.example.app")
    check("title", d["title"] == "Example App")
    check("rating", abs((d["rating"] or 0) - 4.3) < 0.001)
    check("rating_count", d["rating_count"] == 12873)
    check("developer", d["developer"] == "Example Studio")
    check("category", d["category"] == "GAME_PUZZLE")
    check("installs", d["installs"] == "1,000,000+")
    check("source", d["source"] == "google-play")
    # all expected keys present even if null
    for k in ["package","title","rating","rating_count","installs","category","developer","updated","source"]:
        check(f"key present: {k}", k in d)
    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
python3 /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-scrape-play-store.py
```
Expected: FAIL (script missing — `FileNotFoundError` / non-zero exit).

- [ ] **Step 4: Write minimal implementation**

Create `plugins/clone-app/skills/clone-app/scripts/scrape-play-store.py`:
```python
#!/usr/bin/env python3
"""Scrape a Google Play store page into a metrics JSON object.

Primary source is the embedded ld+json SoftwareApplication block (stable).
Falls back to light regex for installs/updated which aren't always in ld+json.
"""
import sys, json, re, argparse, urllib.request

KEYS = ["package", "title", "rating", "rating_count", "installs",
        "category", "developer", "updated", "source"]

def fetch(package):
    url = f"https://play.google.com/store/apps/details?id={package}&hl=en&gl=US"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def parse(html, package):
    out = {k: None for k in KEYS}
    out["package"] = package
    out["source"] = "google-play"

    # ld+json SoftwareApplication block
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>',
                         html, re.DOTALL):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "SoftwareApplication":
            out["title"] = data.get("name")
            auth = data.get("author")
            if isinstance(auth, dict):
                out["developer"] = auth.get("name")
            out["category"] = data.get("applicationCategory")
            ar = data.get("aggregateRating") or {}
            if ar.get("ratingValue") is not None:
                try: out["rating"] = float(ar["ratingValue"])
                except Exception: pass
            if ar.get("ratingCount") is not None:
                try: out["rating_count"] = int(ar["ratingCount"])
                except Exception: pass
            break

    # installs (e.g. "1,000,000+")
    m = re.search(r'([\d,]+\+)\s*<span>\s*Downloads', html)
    if m:
        out["installs"] = m.group(1)

    # updated date (e.g. "Updated on<span>Jun 1, 2026</span>")
    m = re.search(r'Updated on\s*<span>([^<]+)</span>', html)
    if m:
        out["updated"] = m.group(1).strip()

    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--html-file")
    args = ap.parse_args()

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()
    else:
        try:
            html = fetch(args.package)
        except Exception as e:
            print(f"ERROR: failed to fetch Play page: {e}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps(parse(html, args.package), indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
python3 /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-scrape-play-store.py
```
Expected: all `PASS`, exit 0.

- [ ] **Step 6: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/skills/clone-app/scripts/scrape-play-store.py \
          plugins/clone-app/tests/test-scrape-play-store.py \
          plugins/clone-app/tests/fixtures/play-sample.html && \
  git commit -m "feat(clone-app): add scrape-play-store.py with ld+json parsing and tests"
```

---

## Task 6: `check-appstore.py` — iOS presence via iTunes Search API

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/check-appstore.py`
- Create: `plugins/clone-app/tests/fixtures/itunes-sample.json`
- Test: `plugins/clone-app/tests/test-check-appstore.py`

**Interfaces:**
- Consumes: `check-appstore.py <search-term>` queries `https://itunes.apple.com/search?term=<term>&entity=software&limit=5`. For testing, `--json-file <path>` reads a local iTunes response instead of network. (Note: there is no Android package → App Store ID mapping; we search by app title/term, best-effort.)
- Produces: prints JSON to stdout: `{ "found": bool, "source": "app-store", "results": [ {"name","seller","rating","rating_count","price","url"} ... ] }`. On network error without `--json-file`: still prints `{"found": false, "source":"app-store", "results": [], "error": "..."}` and exit 0 (App Store absence is non-fatal per spec).

- [ ] **Step 1: Create the test fixture**

Create `plugins/clone-app/tests/fixtures/itunes-sample.json`:
```json
{
  "resultCount": 1,
  "results": [
    {
      "trackName": "Example App",
      "sellerName": "Example Studio",
      "averageUserRating": 4.5,
      "userRatingCount": 8421,
      "formattedPrice": "Free",
      "trackViewUrl": "https://apps.apple.com/app/id123456789"
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `plugins/clone-app/tests/test-check-appstore.py`:
```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "check-appstore.py")
FIXTURE = os.path.join(HERE, "fixtures", "itunes-sample.json")

def main():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "Example App", "--json-file", FIXTURE])
    d = json.loads(out)
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    check("found true", d["found"] is True)
    check("source", d["source"] == "app-store")
    check("one result", len(d["results"]) == 1)
    r = d["results"][0]
    check("name", r["name"] == "Example App")
    check("seller", r["seller"] == "Example Studio")
    check("rating", abs(r["rating"] - 4.5) < 0.001)
    check("rating_count", r["rating_count"] == 8421)
    check("price", r["price"] == "Free")
    check("url", r["url"].endswith("id123456789"))
    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
python3 /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-check-appstore.py
```
Expected: FAIL (script missing).

- [ ] **Step 4: Write minimal implementation**

Create `plugins/clone-app/skills/clone-app/scripts/check-appstore.py`:
```python
#!/usr/bin/env python3
"""Best-effort check whether an iOS App Store equivalent exists, via the
public iTunes Search API. There is no reliable Android-package → App-Store-ID
mapping, so we search by term (app title) and return the top matches."""
import sys, json, argparse, urllib.request, urllib.parse

def fetch(term):
    q = urllib.parse.urlencode({"term": term, "entity": "software", "limit": 5})
    url = f"https://itunes.apple.com/search?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def shape(data):
    results = []
    for r in data.get("results", []):
        results.append({
            "name": r.get("trackName"),
            "seller": r.get("sellerName"),
            "rating": r.get("averageUserRating"),
            "rating_count": r.get("userRatingCount"),
            "price": r.get("formattedPrice"),
            "url": r.get("trackViewUrl"),
        })
    return {"found": len(results) > 0, "source": "app-store", "results": results}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("term")
    ap.add_argument("--json-file")
    args = ap.parse_args()

    if args.json_file:
        with open(args.json_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        try:
            data = fetch(args.term)
        except Exception as e:
            print(json.dumps({"found": False, "source": "app-store",
                              "results": [], "error": str(e)}, indent=2))
            sys.exit(0)

    print(json.dumps(shape(data), indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
python3 /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/test-check-appstore.py
```
Expected: all `PASS`, exit 0.

- [ ] **Step 6: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/skills/clone-app/scripts/check-appstore.py \
          plugins/clone-app/tests/test-check-appstore.py \
          plugins/clone-app/tests/fixtures/itunes-sample.json && \
  git commit -m "feat(clone-app): add check-appstore.py iTunes search with tests"
```

---

## Task 7: Test runner aggregator

**Files:**
- Create: `plugins/clone-app/tests/run-all.sh`

**Interfaces:**
- Produces: `run-all.sh` runs every test (bash + python), prints a summary, exits non-zero if any fail.

- [ ] **Step 1: Write the runner**

Create `plugins/clone-app/tests/run-all.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
fail=0

echo "=== bash tests ==="
for t in "$HERE"/test-*.sh; do
  echo "--- $(basename "$t") ---"
  bash "$t" || fail=1
done

echo "=== python tests ==="
for t in "$HERE"/test-*.py; do
  echo "--- $(basename "$t") ---"
  python3 "$t" || fail=1
done

echo
if [[ "$fail" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit $fail
```

- [ ] **Step 2: Run it**

Run:
```bash
chmod +x /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/run-all.sh && \
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/run-all.sh
```
Expected: `ALL TESTS PASSED`, exit 0 (all of Tasks 2–6 green).

- [ ] **Step 3: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/tests/run-all.sh && \
  git commit -m "test(clone-app): add aggregate test runner"
```

---

## Task 8: Reference docs — effort, infra cost, stack, report template

**Files:**
- Create: `plugins/clone-app/skills/clone-app/references/stack-recommendation-guide.md`
- Create: `plugins/clone-app/skills/clone-app/references/effort-estimation-guide.md`
- Create: `plugins/clone-app/skills/clone-app/references/infra-cost-guide.md`
- Create: `plugins/clone-app/skills/clone-app/references/report-template.md`

**Interfaces:**
- Produces: four reference docs the SKILL.md links into during Phases 4–6. No code; these are the judgment rubrics that keep AI output consistent.

- [ ] **Step 1: Write the stack recommendation guide**

Create `plugins/clone-app/skills/clone-app/references/stack-recommendation-guide.md`:
```markdown
# Stack Recommendation Guide (Phase 4)

Goal: present the user 2-3 concrete stack options for building the clone, then
let them pick. The pick locks effort + cost math in Phase 5.

## Inputs you have
- Detected original framework (from RE fingerprint): Native Kotlin/Java, Flutter, React Native, etc.
- Detected HTTP stack + backend signals (Retrofit/Ktor/Apollo/GraphQL/WebSocket).
- Feature surface (screen count, SDKs, permissions).

## How to choose the 2-3 options
Always include:
1. **Fastest for AI-assisted dev** — default to **Flutter** (single codebase, strong AI codegen, fast UI) unless the app is heavily native-platform-dependent.
2. **JS-ecosystem option** — **React Native + Expo** when the team is JS-leaning or web reuse matters.
3. **Match-the-original** — only when the original's nativeness is essential (deep platform APIs, AR, heavy native SDKs). Note the higher effort.

## Backend
- If RE shows first-party API hosts → a backend is required. Recommend **Node/TS (NestJS or Express)** or **Supabase** (fastest with AI) unless GraphQL detected → recommend **Apollo Server** or **Hasura**.
- If only third-party hosts (Firebase, payment SDKs) → likely **BaaS / no custom backend**; note it.

## Output format to the user
Present a short table: Option | Mobile stack | Backend | Why | Relative effort (Low/Med/High).
Then ask: "Which stack should I base the effort + cost estimate on?"
```

- [ ] **Step 2: Write the effort estimation guide**

Create `plugins/clone-app/skills/clone-app/references/effort-estimation-guide.md`:
```markdown
# Effort Estimation Guide (Phase 5) — AI-Assisted Units

Estimate in **AI Sprints**, NOT human days. 1 AI Sprint = one focused Claude
Code session producing a reviewable increment (~2-4h human review time).

## Method
1. Build the feature list from RE output:
   - Screens = Activity + Fragment count (dedupe obvious base classes).
   - API surface = endpoint count from find-api-calls.
   - Integrations = third-party SDKs (auth, payment, maps, analytics, push, chat).
   - Backend = REST/GraphQL/WebSocket presence + first-party host count.
2. Assign each feature a complexity and sprint range using the table below.
3. Sum to a range (min–max sprints). Never give a single false-precise number.

## Reference sprint costs
| Feature class | Low | Typical | High | Notes |
|---|---|---|---|---|
| Project scaffold + CI | 0.5 | 1 | 1 | nav, theming, state mgmt setup |
| Auth (email/social) | 1 | 1.5 | 2 | +1 if custom backend auth |
| Simple list/detail screen | 0.3 | 0.5 | 1 | per screen, AI-fast |
| Complex interactive screen | 1 | 2 | 3 | maps, editors, realtime |
| API integration layer | 1 | 2 | 3 | scales with endpoint count |
| Each major SDK integration | 0.5 | 1 | 2 | payment > maps > analytics |
| Custom backend (CRUD) | 2 | 4 | 8 | scales with entity + endpoint count |
| Realtime (WebSocket/push) | 1 | 2 | 4 | |
| Offline/sync | 2 | 3 | 5 | |
| Polish/QA/store submission | 1 | 2 | 3 | |

## Obfuscation caveat
If RE flagged heavy R8/Flutter (feature list incomplete), add a **+20-40%
uncertainty band** and state it explicitly in the report.

## Output
A table: Category | Complexity | Sprints (min–max), then a TOTAL row.
```

- [ ] **Step 3: Write the infra cost guide**

Create `plugins/clone-app/skills/clone-app/references/infra-cost-guide.md`:
```markdown
# Infrastructure Cost Guide (Phase 5)

Estimate **monthly USD** at three scales: MVP (<1k MAU), Growth (~50k MAU),
Scale (~500k MAU). Use round heuristics; mark assumptions.

## Components
| Component | MVP | Growth | Scale | Notes |
|---|---|---|---|---|
| App hosting/backend | $0-20 | $50-200 | $500-2k | Railway/Render/Fly → AWS/GCP |
| Managed DB (Postgres) | $0-15 | $50-150 | $300-1k | Supabase/Neon/RDS |
| Object storage/CDN | $0-5 | $20-80 | $200-800 | S3+CloudFront/Cloudflare |
| Auth (managed) | $0 | $0-100 | $200-500 | Supabase/Auth0 tiers |
| Push notifications | $0 | $0-50 | $50-300 | FCM free; OneSignal paid tiers |
| Third-party APIs | varies | varies | varies | maps, SMS, payments % |
| Monitoring | $0 | $20-50 | $100-300 | Sentry/Datadog |

## Third-party cost flags from RE
- Maps SDK → Google Maps billing after free tier.
- Payment SDK → % per transaction (Stripe ~2.9%+30¢).
- SMS/OTP → per-message (Twilio).
List each detected paid dependency explicitly.

## Output
A 3-column (MVP/Growth/Scale) monthly cost table + a one-line "biggest cost driver".
```

- [ ] **Step 4: Write the report template**

Create `plugins/clone-app/skills/clone-app/references/report-template.md`:
```markdown
# Clone Feasibility Report — {APP_TITLE}

**Package:** {PACKAGE}
**Date:** {DATE}
**Analyzed by:** clone-app skill

## 1. App Overview
- Title / developer / category / installs / rating ({RATING} from {RATING_COUNT} reviews)
- iOS App Store presence: {YES/NO + link}
- One-paragraph description of what the app does.

## 2. Tech Stack (Detected)
- Mobile framework: {framework} (RE fingerprint marker: {marker})
- HTTP stack: {Retrofit/Ktor/...}
- Backend signals: {first-party hosts, REST/GraphQL/WS}
- Notable SDKs: {list}
- Obfuscation level: {low/med/high} — analysis completeness caveat if high.

## 3. Recommended Clone Stack
- Selected by user: {stack}
- Rationale: {1-2 lines}

## 4. Feature List (from APK)
- Screens: {n}
- API endpoints: {n} (key ones listed)
- Integrations: {list}
- Backend required: {yes/no + why}

## 5. Effort Estimate (AI-Assisted)
{effort table from effort-estimation-guide}
**Total: {min}–{max} AI Sprints** (1 sprint ≈ one focused Claude Code session).
Uncertainty band: {±%} due to {reason}.

## 6. Infrastructure Cost Estimate (monthly)
{MVP/Growth/Scale table from infra-cost-guide}
Biggest cost driver: {item}.

## 7. Market Analysis
- Current app metrics: installs {x}, rating {y}, review velocity {if known}.
- Competitor landscape: {2-4 named competitors}.
- Target market size: {rough estimate + basis}.
- Differentiation opportunities: {list}.

## 8. Viability Verdict
**{GO / CONDITIONAL GO / NO GO}**
- Key risks: {list}
- Key opportunities: {list}
- Recommendation rationale: {2-3 sentences tying effort+cost vs market}.

## 9. Next Step
{Link to implementation plan if user proceeds, else "report only".}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/skills/clone-app/references/ && \
  git commit -m "docs(clone-app): add stack/effort/infra/report reference guides"
```

---

## Task 9: Orchestrator SKILL.md — all 8 phases

**Files:**
- Create: `plugins/clone-app/skills/clone-app/SKILL.md`

**Interfaces:**
- Consumes: all helper scripts (Tasks 2-6), the RE script dir (Task 3 resolver), and reference docs (Task 8). Uses `${CLAUDE_PLUGIN_ROOT}` for its own scripts.
- Produces: the activatable skill that runs the full Phase 0-7 workflow. Trigger phrases + frontmatter so Claude Code auto-loads it.

- [ ] **Step 1: Write SKILL.md**

Create `plugins/clone-app/skills/clone-app/SKILL.md`:
```markdown
---
description: Analyze a Google Play app to assess cloning it — download the APK, reverse engineer the tech stack and APIs, analyze app-store presence, estimate AI-assisted build effort and infrastructure cost, judge market viability, and optionally generate an implementation plan. Use when the user gives a Google Play URL or package name and wants a clone feasibility analysis, effort estimate, or tech-stack breakdown. 中文触发词：克隆应用、复刻这个app、分析可行性、估算开发量、克隆可行性分析
trigger: clone app|clone this app|clone feasibility|feasibility analysis|estimate effort to build|reverse engineer and clone|analyze this play store app|can I clone|克隆应用|复刻|可行性分析
---

# Clone App — Feasibility & Effort Analysis

Take a Google Play URL (or package name), reverse engineer the app, analyze its
market, estimate AI-assisted clone effort and infrastructure cost, and produce a
viability report. If the user approves, hand off to the writing-plans skill to
generate a full implementation plan.

This skill orchestrates 8 phases. Deterministic steps are factored into helper
scripts under `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/`. Reverse
engineering reuses the sibling `android-reverse-engineering` plugin's scripts.

## Legal note
Only analyze apps you are authorized to (your own, or for lawful interoperability
/ research). Surface this to the user if intent is unclear. Do not proceed for
clearly infringing intent.

## Phase 0: Input & Validation

Extract the package name:
```bash
PKG="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/extract-package.sh "<user-input>")"
```
If it exits non-zero, ask the user for the package name directly, then re-run.

Create the working dir: `WORK="./work/$PKG"` and `mkdir -p "$WORK"`.

## Phase 1: APK Download

```bash
APK="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/download-apk.sh "$PKG" "$WORK")"
```
The script retries 3× and prints the path (`app.apk` or `app.xapk`). If it exits
non-zero, tell the user the download failed and ask for a local APK/XAPK path;
set `APK` to that path.

## Phase 2: Reverse Engineering

Resolve the sibling RE scripts:
```bash
RE="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/resolve-re-scripts.sh)"
```
If it exits non-zero, show its error (RE plugin not installed) and stop.

Run, in order, reading each output before the next:
1. `bash "$RE/fingerprint.sh" "$APK"` — framework, HTTP stack, obfuscation, SDKs, native libs.
   - **If framework is Flutter / React Native / Cordova / Xamarin:** tell the user Java
     decompilation is limited; proceed but rely on manifest + strings + hardcoded URLs +
     the fingerprint SDK list. Skip steps 3-5's deep API extraction expectations.
2. `bash "$RE/check-deps.sh"` — parse `INSTALL_REQUIRED:` / `INSTALL_OPTIONAL:` lines.
   Install required deps with `bash "$RE/install-dep.sh" <dep>`; re-run check-deps until clean.
   Ask the user before installing optional deps (vineflower, dex2jar).
3. `bash "$RE/decompile.sh" "$APK"` (add `--deobf` if fingerprint showed heavy obfuscation).
   Output lands under the RE script's `output/` — note the `sources/` path it prints.
4. If the app is Kotlin: `bash "$RE/recover-kotlin-names.sh" <sources> "$WORK/output/names/"`.
5. `bash "$RE/find-api-calls.sh" <sources>` (full scan; add `--ktor`/`--apollo`/`--paths` as
   the fingerprint suggests).

From these outputs assemble: framework, HTTP stack, **API endpoint list**,
first-party vs third-party hosts, AndroidManifest summary (permissions, components),
and a **feature list** (screen count, SDKs, backend signals). Keep this in context
for later phases.

## Phase 3: Store Analysis

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/scrape-play-store.py "$PKG" > "$WORK/play.json"
```
Read `play.json` for rating, rating_count, installs, category, developer, updated.
Use the `title` to check iOS:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/check-appstore.py "<title>" > "$WORK/appstore.json"
```
If Play scrape returned mostly nulls (page layout changed), fall back to a web
search for the app's metrics and note the source. App Store absence is fine —
continue with Google Play data only.

## Phase 4: Stack Recommendation

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/stack-recommendation-guide.md`.
Using the RE results + store data, present 2-3 stack options as a table and ask
the user to choose. **Wait for the user's choice before Phase 5.** Lock it.

## Phase 5: Effort & Cost Estimation

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/effort-estimation-guide.md`
and `infra-cost-guide.md`. Build:
- the feature list → AI-Sprint effort table (min-max total, uncertainty band),
- the MVP/Growth/Scale monthly infra cost table.
Base both on the **user-selected stack** from Phase 4.

## Phase 6: Market Viability Report

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/report-template.md`.
Fill every section from the data gathered. For market analysis (competitors,
market size), use web search as needed. Produce a GO / CONDITIONAL GO / NO GO
verdict tying effort + cost against market opportunity.

Write the report:
```
$WORK/clone-report-<YYYY-MM-DD>.md
```
(Use the actual run date.) Show the user a concise summary + the verdict.

## Phase 7: Decision Gate

Ask: "Report saved to `$WORK/clone-report-<date>.md`. Proceed to build the
implementation plan?"
- **Yes** → invoke the `superpowers:writing-plans` skill, passing the report as
  context (the selected stack, feature list, and effort table become the plan's spec).
- **No** → stop; the report stands on its own.

## Error Handling Summary
| Scenario | Action |
|---|---|
| Package not in URL | ask user for package name |
| Download fails 3× | ask for local APK path |
| RE plugin missing | show resolver error, stop |
| Flutter/RN/Cordova/Xamarin | warn, continue with limited RE |
| App Store not found | continue Google Play only |
| Play scrape returns nulls | web-search fallback, note source |
| Heavy obfuscation | add uncertainty band, note in report |
| writing-plans unavailable | write the plan as Markdown manually |
```

- [ ] **Step 2: Validate frontmatter + links**

Run:
```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
python3 - <<'EOF'
import re, sys, os
p = "plugins/clone-app/skills/clone-app/SKILL.md"
s = open(p, encoding="utf-8").read()
assert s.startswith("---"), "missing frontmatter"
fm = s.split("---",2)[1]
assert "description:" in fm and "trigger:" in fm, "frontmatter keys missing"
# every referenced script/reference path under the plugin must exist
base = "plugins/clone-app/skills/clone-app"
for rel in ["scripts/extract-package.sh","scripts/download-apk.sh",
            "scripts/resolve-re-scripts.sh","scripts/scrape-play-store.py",
            "scripts/check-appstore.py","references/stack-recommendation-guide.md",
            "references/effort-estimation-guide.md","references/infra-cost-guide.md",
            "references/report-template.md"]:
    assert os.path.isfile(os.path.join(base, rel)), f"missing {rel}"
print("OK")
EOF
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/skills/clone-app/SKILL.md && \
  git commit -m "feat(clone-app): add orchestrator SKILL.md (phases 0-7)"
```

---

## Task 10: `/clone-app` slash command + README

**Files:**
- Create: `plugins/clone-app/commands/clone-app.md`
- Create: `plugins/clone-app/README.md`

**Interfaces:**
- Consumes: SKILL.md (Task 9).
- Produces: the user-invocable `/clone-app <url>` command and install/usage docs.

- [ ] **Step 1: Write the command file**

Create `plugins/clone-app/commands/clone-app.md`:
```markdown
---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, WebFetch, WebSearch, Skill
description: Analyze a Google Play app for cloning — RE, effort, market viability, optional plan
user-invocable: true
argument-hint: <Google Play URL or package name>
argument: Google Play URL or package name (optional)
---

# /clone-app

Run the full clone-feasibility workflow on a Google Play app.

## Instructions

Follow the clone-app skill workflow in
`${CLAUDE_PLUGIN_ROOT}/skills/clone-app/SKILL.md` exactly, phases 0 through 7.

### Step 1: Get the target
If the user passed a URL or package name as an argument, use it. Otherwise ask
for the Google Play URL or package name.

### Step 2: Run the skill
Execute Phase 0 → Phase 7 from SKILL.md. Pause for the user at:
- Phase 4 (stack choice),
- Phase 7 (proceed to implementation plan?).

Honor the Error Handling Summary table in SKILL.md at every phase.

### Step 3: Deliver
Ensure the report is written to `./work/<package>/clone-report-<date>.md` and
summarize the verdict. If the user approves at Phase 7, invoke
`superpowers:writing-plans` with the report as the spec.
```

- [ ] **Step 2: Write the README**

Create `plugins/clone-app/README.md`:
```markdown
# clone-app — Clone Feasibility Analyzer (Claude Code skill)

Give it a Google Play URL. It downloads the APK, reverse engineers the tech
stack and APIs (via the sibling `android-reverse-engineering` plugin), analyzes
the app's store presence, estimates **AI-assisted** build effort (in AI Sprints)
and monthly infrastructure cost, judges market viability (GO / CONDITIONAL GO /
NO GO), and — if you approve — generates a full implementation plan.

## Requirements
- The `android-reverse-engineering` plugin (ships in this same repo).
- Java JDK 17+ and jadx (the RE plugin auto-installs jadx if missing).
- `curl`, Python 3 (stdlib only), `unzip`.

## Install
```text
/plugin marketplace add /path/to/this/repo
/plugin install android-reverse-engineering@android-reverse-engineering-skill
/plugin install clone-app@android-reverse-engineering-skill
```

## Usage
```text
/clone-app https://play.google.com/store/apps/details?id=com.example.app
```
Or natural language: "Analyze this Play Store app for cloning: <url>".

The skill pauses twice for your input: choosing the clone stack, and deciding
whether to generate the implementation plan.

## Output
```
./work/<package>/
├── app.apk | app.xapk
├── output/            # decompiled sources + Kotlin name maps
├── play.json          # store metrics
├── appstore.json      # iOS presence
└── clone-report-YYYY-MM-DD.md
```

## Keeping the RE plugin up to date
This repo is a fork. To pull upstream improvements:
```bash
git remote add upstream https://github.com/SimoneAvogadro/android-reverse-engineering-skill.git
git pull upstream master
```
The clone-app plugin lives in its own directory, so upstream updates to
`android-reverse-engineering` merge cleanly.

## Legal
For lawful use only — your own apps, authorized interoperability, security
research, or education. You are responsible for compliance.
```

- [ ] **Step 3: Validate command frontmatter**

Run:
```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
python3 -c "
s=open('plugins/clone-app/commands/clone-app.md',encoding='utf-8').read()
assert s.startswith('---') and 'user-invocable: true' in s and 'allowed-tools:' in s
print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/commands/clone-app.md plugins/clone-app/README.md && \
  git commit -m "feat(clone-app): add /clone-app command and README"
```

---

## Task 11: End-to-end smoke test + final verification

**Files:**
- Create: `plugins/clone-app/tests/smoke-structure.sh`

**Interfaces:**
- Produces: a structural smoke test verifying the whole plugin is wired correctly (all files present, all scripts executable, JSON valid, full test suite green). No network — this validates the package, not a live download.

- [ ] **Step 1: Write the smoke test**

Create `plugins/clone-app/tests/smoke-structure.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # repo root
P="$ROOT/plugins/clone-app"
fail=0
must_exist() { [[ -e "$1" ]] && echo "PASS exists: ${1#$ROOT/}" || { echo "FAIL missing: ${1#$ROOT/}"; fail=1; }; }
must_exec()  { [[ -x "$1" ]] && echo "PASS exec: ${1#$ROOT/}"   || { echo "FAIL not exec: ${1#$ROOT/}"; fail=1; }; }

must_exist "$P/.claude-plugin/plugin.json"
must_exist "$P/skills/clone-app/SKILL.md"
must_exist "$P/commands/clone-app.md"
must_exist "$P/README.md"
for s in extract-package.sh download-apk.sh resolve-re-scripts.sh; do
  must_exist "$P/skills/clone-app/scripts/$s"; must_exec "$P/skills/clone-app/scripts/$s"
done
for s in scrape-play-store.py check-appstore.py; do
  must_exist "$P/skills/clone-app/scripts/$s"
done
for r in stack-recommendation-guide effort-estimation-guide infra-cost-guide report-template; do
  must_exist "$P/skills/clone-app/references/$r.md"
done

# JSON validity
python3 -c "import json;json.load(open('$P/.claude-plugin/plugin.json'));json.load(open('$ROOT/.claude-plugin/marketplace.json'))" \
  && echo "PASS json valid" || { echo "FAIL json invalid"; fail=1; }

# clone-app present in marketplace
python3 -c "
import json;d=json.load(open('$ROOT/.claude-plugin/marketplace.json'))
names=[p['name'] for p in d['plugins']]
assert 'clone-app' in names and 'android-reverse-engineering' in names
print('PASS marketplace has both plugins')" || { echo "FAIL marketplace entries"; fail=1; }

exit $fail
```

- [ ] **Step 2: Run smoke + full suite**

Run:
```bash
chmod +x /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/smoke-structure.sh && \
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/smoke-structure.sh && \
bash /Users/fatih.bulut/PythonWorks/clone_app_skill/plugins/clone-app/tests/run-all.sh
```
Expected: smoke test all `PASS`; `ALL TESTS PASSED`. Both exit 0.

- [ ] **Step 3: Verify upstream plugin untouched**

Run:
```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git status --porcelain plugins/android-reverse-engineering/ && \
  echo "---" && \
  git log --oneline -1
```
Expected: the `git status` line for `plugins/android-reverse-engineering/` is **empty** (no modifications to upstream). The `---` separator prints, then the last commit shows.

- [ ] **Step 4: Commit**

```bash
cd /Users/fatih.bulut/PythonWorks/clone_app_skill && \
  git add plugins/clone-app/tests/smoke-structure.sh && \
  git commit -m "test(clone-app): add structural smoke test"
```

- [ ] **Step 5: Final manual checklist (report to user, do not automate)**

Confirm and report:
- [ ] `git pull upstream master` strategy documented in README (Task 10) ✓
- [ ] Upstream `plugins/android-reverse-engineering/` has zero diffs (Step 3) ✓
- [ ] All scripts tested green (Step 2) ✓
- [ ] Skill triggers + command are wired (Tasks 9-10) ✓
- [ ] Recommend the user do ONE live run against a known small app to validate the
      network paths (APKPure download + Play scrape), since those aren't covered by
      offline tests. Suggest: pick a small free app, run `/clone-app <url>`, stop
      after Phase 3 to confirm download + store JSON look right.

---

## Self-Review Notes

**Spec coverage check:**
- Phase 0-7 → Task 9 SKILL.md ✓ (all phases present, in order)
- Repo structure / upstream-untouched → Task 1 + Task 11 Step 3 verification ✓
- APK download w/ retries + xapk detect → Task 4 ✓
- RE script invocation via sibling path → Task 3 resolver + Task 9 Phase 2 ✓
- Store analysis (Play + App Store) → Tasks 5, 6 + Phase 3 ✓
- Stack recommendation (Option C + user choice) → Task 8 guide + Phase 4 ✓
- Effort estimation in AI Sprints → Task 8 guide + Phase 5 ✓
- Infra cost → Task 8 guide + Phase 5 ✓
- Market viability report + GO/NO-GO → Task 8 template + Phase 6 ✓
- Decision gate → writing-plans handoff → Phase 7 ✓
- All error-handling rows → Phase 2/3 + SKILL.md error table ✓
- Known limitations (iOS, obfuscation, install ranges) → reflected in guides/template ✓
- Install instructions → Task 10 README ✓

**Placeholder scan:** No TBD/TODO; all code blocks complete; report-template uses
intentional `{PLACEHOLDER}` tokens that are fill-in fields for runtime, not plan gaps.

**Type/name consistency:** Script names, JSON keys (`package/title/rating/rating_count/
installs/category/developer/updated/source`; `found/source/results/name/seller/rating/
rating_count/price/url`), and env vars (`CLAUDE_PLUGIN_ROOT`, `CLONE_APP_CURL`) match
across tasks. `$WORK`, `$PKG`, `$APK`, `$RE` consistent in SKILL.md.
```
