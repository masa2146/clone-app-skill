# market-research Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `market-research` Claude Code plugin whose `/market-research` skill autonomously scans the app/game market (free web + LLM trend synthesis), produces ≥10 scored, non-repeating clone candidates, and hands each user-chosen candidate to the existing `clone-app` skill.

**Architecture:** A phased prose SKILL.md orchestrator (same shape as `clone-app/SKILL.md`) backed by two stdlib-only Python helper scripts (`fetch-charts.py` for App Store RSS chart data, `history.py` for the non-repeat memory) and three Markdown reference rubrics (`research-angles`, `scoring-guide`, `report-template`). Each script is independently testable offline against `tests/fixtures/`. The plugin is self-contained under `plugins/market-research/`; the only shared-file edit is adding one entry to root `.claude-plugin/marketplace.json`.

**Tech Stack:** Bash (`#!/usr/bin/env bash`), Python 3 stdlib only (`urllib`, `json`, `argparse`, `ssl`, `subprocess`, `shutil`), Markdown skill/command/reference docs. No pip, no virtualenv.

## Global Constraints

- **Never modify `plugins/android-reverse-engineering/`** — `git status --porcelain plugins/android-reverse-engineering/` must print nothing before any commit.
- **Python is stdlib-only** — `urllib`, `json`, `re`, `argparse`, `ssl`, `subprocess`, `shutil`. No pip, no virtualenv.
- **All scripts** use `#!/usr/bin/env bash` or `#!/usr/bin/env python3`; bash scripts are invoked with `bash <path>`, not `sh`.
- **Bash tests** use `set -uo pipefail` (not `-e`), aggregate failures into a `fail` var so every assertion runs, and `exit $fail`.
- **Python network scripts** must support an offline flag (`--json-file`) and be tested against `tests/fixtures/` — never hitting the network in tests.
- **Working dir** at runtime is `./work/market-research/` relative to the user's cwd — never inside the plugin.
- **Effort** is measured in "AI Sprints" (one focused Claude session), never calendar time.
- **Commits** follow Conventional Commits scoped to the plugin: `feat(market-research): …`, `test(market-research): …`.
- **HTTP GETs** copy the existing clone-app pattern: try `urllib` with `User-Agent: "Mozilla/5.0"`, fall back to system `curl` on an `ssl.SSLError` (macOS system Python ships without a CA bundle).
- **Candidate identity key** is the package if present, else the lowercased, stripped name. This key is used identically by `history.py` dedup and by the SKILL's handoff. Defined in Task 3, reused in Task 5.

---

### Task 1: Plugin scaffold + structural smoke test

Create the plugin skeleton (manifest, command, README), register it in the marketplace, and add a structural smoke test that locks the file layout in place. Later tasks fill the scripts/references/skill this test expects, so the smoke test is written now but its script/reference/skill assertions will only fully pass once Tasks 2–5 land — Step 4 below runs only the subset that exists after this task.

**Files:**
- Create: `plugins/market-research/.claude-plugin/plugin.json`
- Create: `plugins/market-research/commands/market-research.md`
- Create: `plugins/market-research/README.md`
- Create: `plugins/market-research/tests/smoke-structure.sh`
- Modify: `.claude-plugin/marketplace.json` (append one plugin entry)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: the directory layout `plugins/market-research/{.claude-plugin,commands,skills/market-research/{scripts,references},tests/fixtures}` that all later tasks write into; the marketplace entry `name: "market-research"`.

- [ ] **Step 1: Write the plugin manifest**

Create `plugins/market-research/.claude-plugin/plugin.json`:

```json
{
  "name": "market-research",
  "version": "0.1.0",
  "description": "Autonomously research the app/game market (free web + LLM trend synthesis) and surface scored, non-repeating clone candidates that feed into the clone-app skill.",
  "author": {
    "name": "masa2146"
  },
  "repository": "https://github.com/masa2146/clone-app-skill",
  "license": "Apache-2.0",
  "keywords": ["market-research", "app-discovery", "trends", "clone", "play-store", "app-store"],
  "skills": "./skills/",
  "commands": "./commands/"
}
```

- [ ] **Step 2: Write the slash command**

Create `plugins/market-research/commands/market-research.md`:

```markdown
---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, WebFetch, WebSearch, Skill
description: Research the app/game market and surface scored, non-repeating clone candidates
user-invocable: true
argument-hint: [optional focus, e.g. "casual games" or "fintech LATAM"]
argument: optional market focus or angle (optional)
---

# /market-research

Run the market-research workflow: scan the market, score candidates, hand picks to clone-app.

## Instructions

Follow the market-research skill workflow in
`${CLAUDE_PLUGIN_ROOT}/skills/market-research/SKILL.md` exactly, phases 0 through 5.

### Step 1: Optional focus
If the user passed a focus argument (e.g. "casual games", "fintech LATAM"), bias
the Phase 0 seed selection toward it. Otherwise rotate seeds normally.

### Step 2: Run the skill
Execute Phase 0 → Phase 5 from SKILL.md. Pause for the user at Phase 5 (pick
candidates to hand to clone-app).

### Step 3: Deliver
Ensure the report is written to `./work/market-research/research-<date>.md` and
the new suggestions are appended to `./work/market-research/history.json`. For
each candidate the user picks, resolve it to a Google Play package/URL and invoke
the `clone-app` skill on it.
```

- [ ] **Step 3: Write the README**

Create `plugins/market-research/README.md`:

```markdown
# market-research

A Claude Code plugin that autonomously researches the app/game market and surfaces
scored, non-repeating clone candidates, then hands user-chosen candidates to the
`clone-app` plugin for feasibility analysis.

## What it does

`/market-research` runs a 6-phase workflow:

0. **Seed rotation** — pick varied search angles (category × region × niche) so runs differ.
1. **Gather** — App Store RSS chart data (`fetch-charts.py`) + free web search for trends.
2. **Synthesize** — cluster findings into ≥10 distinct app/game ideas.
3. **Score** — composite score: cloneability + market opportunity + monetization fit.
4. **Dedup** — exclude anything already in `./work/market-research/history.json`.
5. **Present + handoff** — show the ranked table; chosen candidates flow into `clone-app`.

## State

Written under `./work/market-research/` in your current directory:
- `history.json` — every past suggestion; the non-repeat memory.
- `research-<date>.md` — the full report for a run.

## Scripts

- `scripts/fetch-charts.py` — fetch App Store RSS chart feeds → normalized JSON.
- `scripts/history.py` — read / append / dedup the suggestion history.

Python is stdlib-only. Tests run offline against `tests/fixtures/`:

```bash
bash plugins/market-research/tests/run-all.sh
```

## Effort convention

Effort is measured in **AI Sprints** (one focused Claude session), never calendar time.
```

- [ ] **Step 4: Append the marketplace entry**

In `.claude-plugin/marketplace.json`, add a third object to the `plugins` array, after the `clone-app` entry (keep the existing two entries byte-identical). The new entry:

```json
{
  "name": "market-research",
  "source": "./plugins/market-research",
  "description": "Research the app/game market and surface scored, non-repeating clone candidates that feed into clone-app.",
  "version": "0.1.0",
  "author": {
    "name": "masa2146"
  },
  "repository": "https://github.com/masa2146/clone-app-skill",
  "license": "Apache-2.0",
  "keywords": ["market-research", "app-discovery", "trends", "clone"],
  "category": "security"
}
```

- [ ] **Step 5: Write the structural smoke test**

Create `plugins/market-research/tests/smoke-structure.sh`. It checks the full intended layout (including files created in Tasks 2–5) so it doubles as the plugin's final structural gate; everything is asserted now and the later tasks make it fully green.

```bash
#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # repo root
P="$ROOT/plugins/market-research"
fail=0
must_exist() { [[ -e "$1" ]] && echo "PASS exists: ${1#$ROOT/}" || { echo "FAIL missing: ${1#$ROOT/}"; fail=1; }; }
must_exec()  { [[ -x "$1" ]] && echo "PASS exec: ${1#$ROOT/}"   || { echo "FAIL not exec: ${1#$ROOT/}"; fail=1; }; }

must_exist "$P/.claude-plugin/plugin.json"
must_exist "$P/commands/market-research.md"
must_exist "$P/README.md"
must_exist "$P/skills/market-research/SKILL.md"
for s in fetch-charts.py history.py; do
  must_exist "$P/skills/market-research/scripts/$s"
  must_exec  "$P/skills/market-research/scripts/$s"
done
for r in research-angles scoring-guide report-template; do
  must_exist "$P/skills/market-research/references/$r.md"
done

# JSON validity: plugin manifest + marketplace
python3 -c "import json;json.load(open('$P/.claude-plugin/plugin.json'));json.load(open('$ROOT/.claude-plugin/marketplace.json'))" \
  && echo "PASS json valid" || { echo "FAIL json invalid"; fail=1; }

# all three plugins present in marketplace
python3 -c "
import json;d=json.load(open('$ROOT/.claude-plugin/marketplace.json'))
names=[p['name'] for p in d['plugins']]
assert 'market-research' in names and 'clone-app' in names and 'android-reverse-engineering' in names
print('PASS marketplace has all three plugins')" || { echo "FAIL marketplace entries"; fail=1; }

exit $fail
```

- [ ] **Step 6: Make the test executable and create empty dirs**

Run:
```bash
chmod +x plugins/market-research/tests/smoke-structure.sh
mkdir -p plugins/market-research/skills/market-research/scripts \
         plugins/market-research/skills/market-research/references \
         plugins/market-research/tests/fixtures
```

- [ ] **Step 7: Verify upstream untouched + marketplace valid**

Run:
```bash
git status --porcelain plugins/android-reverse-engineering/
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); print('marketplace OK')"
```
Expected: the `git status` line prints **nothing**; the python prints `marketplace OK`.

- [ ] **Step 8: Commit**

```bash
git add plugins/market-research/.claude-plugin plugins/market-research/commands \
        plugins/market-research/README.md plugins/market-research/tests/smoke-structure.sh \
        .claude-plugin/marketplace.json
git commit -m "feat(market-research): scaffold plugin, command, README, marketplace entry"
```

---

### Task 2: `fetch-charts.py` — App Store RSS chart fetcher

Fetch and normalize Apple's public App Store RSS chart feeds (top free / top paid / top grossing) into a flat JSON list of ranked entries. This is the only hard chart data the skill ingests; trend signal beyond it comes from the model's web search in the SKILL prose (not scriptable/testable). iOS bundle IDs are informational only — Android package resolution happens later in the skill.

**Files:**
- Create: `plugins/market-research/skills/market-research/scripts/fetch-charts.py`
- Create: `plugins/market-research/tests/fixtures/rss-sample.json`
- Test: `plugins/market-research/tests/test-fetch-charts.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: CLI `python3 fetch-charts.py <feed> [--region us] [--limit 25] [--json-file PATH]` printing `json.dumps(..., indent=2)` of `{"feed","region","count","entries":[...]}`. Each entry is a dict with keys `rank` (int), `name` (str|None), `developer` (str|None), `category` (str|None), `bundle_id` (str|None), `price` (str|None). `<feed>` is one of `topfreeapplications`, `toppaidapplications`, `topgrossingapplications`.

- [ ] **Step 1: Create the RSS fixture**

Create `plugins/market-research/tests/fixtures/rss-sample.json` — a trimmed but structurally faithful Apple RSS JSON with two entries:

```json
{
  "feed": {
    "entry": [
      {
        "im:name": { "label": "Puzzle Quest Saga" },
        "im:artist": { "label": "Casual Studio" },
        "category": { "attributes": { "label": "Games", "im:id": "6014" } },
        "id": { "attributes": { "im:id": "1111111111", "im:bundleId": "com.casual.puzzlequest" } },
        "im:price": { "attributes": { "amount": "0.00000", "currency": "USD" } }
      },
      {
        "im:name": { "label": "Budget Buddy" },
        "im:artist": { "label": "Fintech Labs" },
        "category": { "attributes": { "label": "Finance", "im:id": "6015" } },
        "id": { "attributes": { "im:id": "2222222222", "im:bundleId": "com.fintech.budgetbuddy" } },
        "im:price": { "attributes": { "amount": "0.00000", "currency": "USD" } }
      }
    ]
  }
}
```

- [ ] **Step 2: Write the failing test**

Create `plugins/market-research/tests/test-fetch-charts.py`:

```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "fetch-charts.py")
FIXTURE = os.path.join(HERE, "fixtures", "rss-sample.json")

def run():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "topfreeapplications",
         "--region", "us", "--json-file", FIXTURE])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    check("feed", d["feed"] == "topfreeapplications")
    check("region", d["region"] == "us")
    check("count", d["count"] == 2)
    e0 = d["entries"][0]
    check("rank 1", e0["rank"] == 1)
    check("name", e0["name"] == "Puzzle Quest Saga")
    check("developer", e0["developer"] == "Casual Studio")
    check("category", e0["category"] == "Games")
    check("bundle_id", e0["bundle_id"] == "com.casual.puzzlequest")
    check("price", e0["price"] == "0.00000")
    e1 = d["entries"][1]
    check("rank 2", e1["rank"] == 2)
    check("second name", e1["name"] == "Budget Buddy")
    for k in ["rank", "name", "developer", "category", "bundle_id", "price"]:
        check(f"key present: {k}", k in e0)
    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python3 plugins/market-research/tests/test-fetch-charts.py`
Expected: FAIL — the script file does not exist yet (subprocess raises / non-zero).

- [ ] **Step 4: Write the implementation**

Create `plugins/market-research/skills/market-research/scripts/fetch-charts.py`:

```python
#!/usr/bin/env python3
"""Fetch an Apple App Store RSS chart feed into a normalized JSON list.

Apple publishes public, no-auth RSS chart feeds as JSON at
https://itunes.apple.com/<region>/rss/<feed>/limit=<n>/json . They give a
ranked list of trending apps (name, developer, category, iOS bundle id, price).

This is iOS chart data — bundle ids are iOS bundle ids, NOT Android packages.
The market-research skill uses these as trend signal and resolves a Google Play
package later (Phase 5) before any clone-app handoff. Stdlib-only, no pip.
"""
import sys, json, argparse, urllib.request, ssl, subprocess, shutil

FEEDS = ("topfreeapplications", "toppaidapplications", "topgrossingapplications")
UA = "Mozilla/5.0"

def _http_get(url):
    """GET a URL as text. urllib first; on an SSL trust failure (macOS system
    Python ships without a CA bundle) fall back to system `curl`."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLError):
            raise
        if not shutil.which("curl"):
            raise
        out = subprocess.run(["curl", "-sL", "--fail", "-A", UA, url],
                             capture_output=True, timeout=60)
        if out.returncode != 0:
            raise
        return out.stdout.decode("utf-8", "replace")

def fetch(feed, region, limit):
    url = f"https://itunes.apple.com/{region}/rss/{feed}/limit={limit}/json"
    return json.loads(_http_get(url))

def _label(node):
    """Apple wraps text values as {"label": "..."}; return the label or None."""
    if isinstance(node, dict):
        return node.get("label")
    return None

def normalize(data):
    entries = []
    feed = data.get("feed") or {}
    raw = feed.get("entry") or []
    if isinstance(raw, dict):   # Apple collapses a single entry to a dict
        raw = [raw]
    for i, e in enumerate(raw, start=1):
        cat = (e.get("category") or {}).get("attributes") or {}
        idattr = (e.get("id") or {}).get("attributes") or {}
        price = (e.get("im:price") or {}).get("attributes") or {}
        entries.append({
            "rank": i,
            "name": _label(e.get("im:name")),
            "developer": _label(e.get("im:artist")),
            "category": cat.get("label"),
            "bundle_id": idattr.get("im:bundleId"),
            "price": price.get("amount"),
        })
    return entries

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("feed", choices=FEEDS)
    ap.add_argument("--region", default="us")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json-file")
    args = ap.parse_args()

    if args.json_file:
        with open(args.json_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        try:
            data = fetch(args.feed, args.region, args.limit)
        except Exception as e:
            print(f"ERROR: failed to fetch RSS feed: {e}", file=sys.stderr)
            sys.exit(1)

    entries = normalize(data)
    print(json.dumps({
        "feed": args.feed,
        "region": args.region,
        "count": len(entries),
        "entries": entries,
    }, indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Make it executable and run the test to verify it passes**

Run:
```bash
chmod +x plugins/market-research/skills/market-research/scripts/fetch-charts.py
python3 plugins/market-research/tests/test-fetch-charts.py
```
Expected: every line `PASS`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/market-research/skills/market-research/scripts/fetch-charts.py \
        plugins/market-research/tests/test-fetch-charts.py \
        plugins/market-research/tests/fixtures/rss-sample.json
git commit -m "feat(market-research): add fetch-charts.py App Store RSS fetcher with offline test"
```

---

### Task 3: `history.py` — non-repeat suggestion memory

Maintain `history.json`: the list of every candidate ever suggested, so each run can exclude what it has already proposed. Two subcommands: `filter` (drop already-seen candidates from a list, on stdout) and `add` (append candidates to history). Identity key = package if present, else lowercased/stripped name — the shared key from Global Constraints.

**Files:**
- Create: `plugins/market-research/skills/market-research/scripts/history.py`
- Create: `plugins/market-research/tests/fixtures/history-seed.json`
- Create: `plugins/market-research/tests/fixtures/candidates-sample.json`
- Test: `plugins/market-research/tests/test-history.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `python3 history.py filter --history H.json < candidates.json` → prints the candidates array with already-seen entries removed.
  - `python3 history.py add --history H.json < candidates.json` → appends candidates to `H.json` (creating it if absent), writes the file, prints `{"added": N, "total": M}`.
  - Importable `cand_key(entry) -> str`: returns `entry["package"]` if truthy, else `entry["name"].strip().lower()`. This is the canonical candidate identity used by the SKILL handoff too.
  - A candidate is an object with at least a `name`; `package` is optional.
  - `history.json` on disk is `{"suggestions": [ {key, name, package, date, run_id}, ... ]}`.

- [ ] **Step 1: Create the fixtures**

Create `plugins/market-research/tests/fixtures/history-seed.json`:

```json
{
  "suggestions": [
    { "key": "com.casual.puzzlequest", "name": "Puzzle Quest Saga", "package": "com.casual.puzzlequest", "date": "2026-06-01", "run_id": "seed" },
    { "key": "habit tracker pro", "name": "Habit Tracker Pro", "package": null, "date": "2026-06-01", "run_id": "seed" }
  ]
}
```

Create `plugins/market-research/tests/fixtures/candidates-sample.json` — three candidates, two of which collide with the seed (one by package, one by name-case):

```json
[
  { "name": "Puzzle Quest Saga", "package": "com.casual.puzzlequest", "category": "Games" },
  { "name": "habit tracker PRO", "category": "Productivity" },
  { "name": "Budget Buddy", "package": "com.fintech.budgetbuddy", "category": "Finance" }
]
```

- [ ] **Step 2: Write the failing test**

Create `plugins/market-research/tests/test-history.py`:

```python
#!/usr/bin/env python3
import json, subprocess, sys, os, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "history.py")
FIX = os.path.join(HERE, "fixtures")

def run(args, stdin_path):
    with open(stdin_path, "rb") as f:
        return subprocess.run([sys.executable, SCRIPT, *args],
                              stdin=f, capture_output=True)

def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    cands = os.path.join(FIX, "candidates-sample.json")

    # filter: against the seed, only "Budget Buddy" survives
    r = run(["filter", "--history", os.path.join(FIX, "history-seed.json")], cands)
    check("filter exit 0", r.returncode == 0)
    survivors = json.loads(r.stdout)
    names = sorted(c["name"] for c in survivors)
    check("filter drops package collision + name collision", names == ["Budget Buddy"])

    # filter against a missing history file = nothing seen, all 3 survive
    tmp = tempfile.mkdtemp()
    try:
        missing = os.path.join(tmp, "nope.json")
        r = run(["filter", "--history", missing], cands)
        check("filter missing-history exit 0", r.returncode == 0)
        check("filter missing-history keeps all", len(json.loads(r.stdout)) == 3)

        # add: appends all 3 to a fresh history, reports counts
        h = os.path.join(tmp, "h.json")
        r = run(["add", "--history", h], cands)
        check("add exit 0", r.returncode == 0)
        rep = json.loads(r.stdout)
        check("add reports added 3", rep["added"] == 3)
        check("add reports total 3", rep["total"] == 3)
        saved = json.load(open(h))
        check("history file has 3 suggestions", len(saved["suggestions"]) == 3)
        check("history entries carry key", all("key" in s for s in saved["suggestions"]))
    finally:
        shutil.rmtree(tmp)

    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python3 plugins/market-research/tests/test-history.py`
Expected: FAIL — `history.py` does not exist yet.

- [ ] **Step 4: Write the implementation**

Create `plugins/market-research/skills/market-research/scripts/history.py`:

```python
#!/usr/bin/env python3
"""Non-repeat memory for market-research suggestions.

history.json holds every candidate ever suggested so a run can avoid repeating
itself. Identity key = package if present, else the lowercased/stripped name.

Subcommands (candidates read as a JSON array on stdin):
  filter --history H.json   -> print the candidates minus already-seen ones
  add    --history H.json   -> append candidates to H.json, print {added,total}

Date/run_id for added entries come from --date / --run-id (the skill passes the
run date); both default to empty strings so the script is deterministic and
needs no clock. Stdlib-only, no pip.
"""
import sys, json, argparse, os

def cand_key(entry):
    """Canonical identity for a candidate. Package wins; else lowercased name."""
    pkg = entry.get("package")
    if pkg:
        return str(pkg).strip()
    return str(entry.get("name", "")).strip().lower()

def load_history(path):
    if not os.path.exists(path):
        return {"suggestions": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("suggestions", [])
    return data

def seen_keys(history):
    return {s.get("key") for s in history["suggestions"]}

def read_candidates():
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        raise ValueError("candidates stdin must be a JSON array")
    return data

def cmd_filter(args):
    history = load_history(args.history)
    seen = seen_keys(history)
    cands = read_candidates()
    survivors = [c for c in cands if cand_key(c) not in seen]
    print(json.dumps(survivors, indent=2))

def cmd_add(args):
    history = load_history(args.history)
    seen = seen_keys(history)
    cands = read_candidates()
    added = 0
    for c in cands:
        k = cand_key(c)
        if k in seen:
            continue
        history["suggestions"].append({
            "key": k,
            "name": c.get("name"),
            "package": c.get("package"),
            "date": args.date,
            "run_id": args.run_id,
        })
        seen.add(k)
        added += 1
    os.makedirs(os.path.dirname(os.path.abspath(args.history)), exist_ok=True)
    with open(args.history, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    print(json.dumps({"added": added, "total": len(history["suggestions"])}, indent=2))

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("filter", "add"):
        p = sub.add_parser(name)
        p.add_argument("--history", required=True)
        p.add_argument("--date", default="")
        p.add_argument("--run-id", default="")
    args = ap.parse_args()
    {"filter": cmd_filter, "add": cmd_add}[args.cmd](args)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Make it executable and run the test to verify it passes**

Run:
```bash
chmod +x plugins/market-research/skills/market-research/scripts/history.py
python3 plugins/market-research/tests/test-history.py
```
Expected: every line `PASS`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/market-research/skills/market-research/scripts/history.py \
        plugins/market-research/tests/test-history.py \
        plugins/market-research/tests/fixtures/history-seed.json \
        plugins/market-research/tests/fixtures/candidates-sample.json
git commit -m "feat(market-research): add history.py non-repeat memory with offline test"
```

---

### Task 4: Reference rubrics

Write the three Markdown rubrics the SKILL reads so AI-judgment steps (angle rotation, scoring, report shape) stay consistent and tunable without editing the prose. These are documentation deliverables — no code test beyond the smoke test's existence check (Task 1, Step 5), so this task's gate is that smoke-structure passes their `must_exist` lines.

**Files:**
- Create: `plugins/market-research/skills/market-research/references/research-angles.md`
- Create: `plugins/market-research/skills/market-research/references/scoring-guide.md`
- Create: `plugins/market-research/skills/market-research/references/report-template.md`

**Interfaces:**
- Consumes: the candidate identity concept from Task 3 (scoring-guide references the same `name`/`package` fields).
- Produces: three rubric files the SKILL (Task 5) reads by path. `scoring-guide.md` defines the four score components and their weights that the SKILL's Phase 3 applies. `report-template.md` defines the section order the SKILL's Phase 5 fills.

- [ ] **Step 1: Write the research-angles rubric**

Create `plugins/market-research/skills/market-research/references/research-angles.md`:

```markdown
# Research Angles

A rotating menu of search angles. Each run picks a DIFFERENT combination so
results vary run-to-run (paired with history exclusion). Do not use the same
combination two runs in a row — vary at least the category and the region.

## How to rotate

1. Read `./work/market-research/history.json` if present; note the angles used
   recently (the `run_id` encodes the angle — see SKILL Phase 0).
2. Pick **2–3 categories**, **1–2 regions**, and **1 niche lens** you did NOT use
   last run. If a focus argument was passed to the command, force one category to
   match it.
3. Combine into concrete searches in Phase 1.

## Categories

- Hyper-casual games
- Puzzle / word games
- Productivity & utilities
- Finance / fintech
- Health & fitness
- Education / kids
- Photo & video editing
- AI tools (chat, image, voice)
- Social & community
- Lifestyle / habit

## Regions (App Store RSS region codes)

- `us` (United States)
- `gb` (United Kingdom)
- `br` (Brazil — LATAM signal)
- `in` (India)
- `tr` (Türkiye)
- `id` (Indonesia)
- `de` (Germany)

## Niche lenses

- Underserved language/region (few quality localized apps)
- Dated incumbent (top app last updated > 1 year ago)
- Single-feature breakout (one job done very well)
- Rising trend (news/ProductHunt/Reddit chatter in the last ~90 days)
- Monetization mismatch (popular but weakly monetized → headroom)

## App Store RSS feeds to pull (via fetch-charts.py)

- `topfreeapplications` — demand/popularity signal
- `topgrossingapplications` — monetization signal
- `toppaidapplications` — willingness-to-pay signal
```

- [ ] **Step 2: Write the scoring rubric**

Create `plugins/market-research/skills/market-research/references/scoring-guide.md`:

```markdown
# Scoring Guide

Score every candidate 0–100 as a weighted composite. Three PRIMARY components
(cloneability, market opportunity, monetization fit) plus a secondary tiebreaker
(niche gap). Show the component scores, not just the total, so picks are auditable.

## Components & weights

| Component | Weight | What it measures |
|---|---|---|
| Cloneability | 35% | How cheaply this rebuilds with clone-app + AI. |
| Market opportunity | 35% | Demand, growth, and incumbent weakness. |
| Monetization fit | 20% | Ads/IAP friendliness and category ARPU. |
| Niche gap (tiebreaker) | 10% | Underserved region/language/segment. |

Total = 0.35·clone + 0.35·market + 0.20·monetization + 0.10·niche, each subscore 0–100.

## Scoring each component (0–100)

**Cloneability** — higher = easier:
- 80–100: simple CRUD/utility, few backend endpoints, no heavy ML, standard UI.
- 50–79: moderate backend, some real-time or media, mainstream third-party SDKs.
- 0–49: heavy ML/on-device models, complex real-time/multiplayer, deep native, large content moat.

**Market opportunity** — higher = better:
- 80–100: strong/growing demand, dated or weak incumbents, clear unmet need.
- 50–79: healthy demand, beatable incumbents.
- 0–49: saturated, dominated by entrenched well-funded players.

**Monetization fit** — higher = better:
- 80–100: category with proven ads+IAP and high ARPU (casual games, utilities).
- 50–79: monetizable but moderate ARPU.
- 0–49: hard to monetize / users expect free.

**Niche gap** — higher = more underserved:
- 80–100: clear language/region/segment with no quality option.
- 0–49: well served everywhere.

## Output per candidate

For each candidate keep: `name`, `package` (if resolved), `category`, the four
subscores, the weighted `total`, and a one-line rationale. Rank by `total`
descending. Produce at least 10 candidates AFTER history exclusion.
```

- [ ] **Step 3: Write the report template**

Create `plugins/market-research/skills/market-research/references/report-template.md`:

```markdown
# Market Research Report Template

Fill every section. Write to `./work/market-research/research-<YYYY-MM-DD>.md`.

---

# Market Research — <YYYY-MM-DD>

## Run parameters
- Angles this run: <categories / regions / niche lens chosen in Phase 0>
- Focus argument: <the user's focus, or "none">
- Sources: App Store RSS (<feeds/regions pulled>) + web search (<themes>)
- Candidates after history exclusion: <N> (history had <M> prior suggestions)

## Top candidates (ranked)

| # | Name | Category | Clone | Market | Monet. | Niche | **Total** | Why now |
|---|------|----------|------:|-------:|-------:|------:|----------:|---------|
| 1 | …    | …        |    85 |     80 |     75 |    60 |      **79** | one-line trend rationale |
| … |      |          |       |        |        |       |           |         |

(At least 10 rows.)

## Candidate detail

For each of the top candidates:

### <name>
- **Package (if known):** <com.x.y or "to resolve">
- **What it does:** <1–2 sentences>
- **Why now:** <trend signal: chart movement, news, dated incumbent…>
- **Incumbents:** <who already does this and how weak/strong>
- **Monetization:** <ads / IAP / subscription; ARPU note>
- **Scores:** clone <>, market <>, monetization <>, niche <> → **total <>**
- **Clone risk flags:** <heavy ML / native / content moat / none>

## Recommended picks

Top 3 to send to clone-app first, with one sentence each on why they lead.

## Next step

The user picks one or more candidates; each chosen candidate is resolved to a
Google Play package/URL and handed to the `clone-app` skill for full feasibility.
```

- [ ] **Step 4: Run the structural smoke test (references now exist)**

Run: `bash plugins/market-research/tests/smoke-structure.sh`
Expected: the three `references/*.md` lines now print `PASS exists`. (SKILL.md and the scripts may still show their state per which tasks have run; if Tasks 2–3 are already done, only the SKILL line is still expected to fail until Task 5.)

- [ ] **Step 5: Commit**

```bash
git add plugins/market-research/skills/market-research/references/
git commit -m "feat(market-research): add research-angles, scoring, and report rubrics"
```

---

### Task 5: SKILL.md orchestrator

Write the phased prose workflow Claude executes — the heart of the plugin. It wires the scripts and rubrics into the 6-phase flow and ends by handing user-chosen candidates to `clone-app`. No new code test; its gate is the smoke test (SKILL.md existence) plus a content grep for the phase markers and the clone-app handoff.

**Files:**
- Create: `plugins/market-research/skills/market-research/SKILL.md`
- Test: `plugins/market-research/tests/test-skill-content.sh`

**Interfaces:**
- Consumes: `fetch-charts.py` CLI (Task 2), `history.py filter`/`add` CLI and the `cand_key` rule (Task 3), the three rubrics (Task 4).
- Produces: the executable workflow. Phase 5 invokes the `clone-app` skill per pick. Defines the on-disk state contract: `./work/market-research/history.json` and `./work/market-research/research-<date>.md`.

- [ ] **Step 1: Write the failing content test**

Create `plugins/market-research/tests/test-skill-content.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SKILL="$ROOT/plugins/market-research/skills/market-research/SKILL.md"
fail=0
has() { grep -q "$1" "$SKILL" && echo "PASS contains: $1" || { echo "FAIL missing: $1"; fail=1; }; }

[[ -f "$SKILL" ]] || { echo "FAIL: SKILL.md missing"; exit 1; }
# frontmatter
has "description:"
has "trigger:"
# all six phases
has "Phase 0"
has "Phase 1"
has "Phase 2"
has "Phase 3"
has "Phase 4"
has "Phase 5"
# wires both scripts and the rubrics
has "fetch-charts.py"
has "history.py"
has "scoring-guide.md"
has "research-angles.md"
has "report-template.md"
# state contract + handoff
has "work/market-research"
has "history.json"
has "clone-app"
exit $fail
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash plugins/market-research/tests/test-skill-content.sh`
Expected: FAIL on the first line — `SKILL.md missing`.

- [ ] **Step 3: Write the SKILL.md**

Create `plugins/market-research/skills/market-research/SKILL.md`:

```markdown
---
description: Autonomously research the app and game market — rotate search angles, pull App Store chart feeds, synthesize emerging trends, score candidates by cloneability + market opportunity + monetization fit, exclude anything suggested before, and hand chosen candidates to the clone-app skill. Use when the user wants market research, fresh app/game ideas to clone, trending apps, or "what should I build next". 中文触发词：市场调研、找应用创意、热门应用、值得克隆的app
trigger: market research|app ideas|what to build|what should i clone|trending apps|find apps to clone|top apps|market scan|市场调研|应用创意|热门应用
---

# Market Research — Discover Clone Candidates

Scan the app/game market with free sources, score candidates, and hand the ones
you pick to the `clone-app` skill. Every run rotates its search angles and
excludes everything suggested before, so results stay fresh.

This skill orchestrates 6 phases (0–5). Deterministic steps are factored into
helper scripts under `${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/`;
AI-judgment steps follow rubrics under `.../references/`.

## Legal note
This produces market research and ideas only. Actual cloning is gated later by
the `clone-app` skill's own legal note (analyze only apps you are authorized to).

## State & working dir
All state lives under `./work/market-research/` in the user's cwd (never inside
the plugin):
- `history.json` — every candidate ever suggested (the non-repeat memory).
- `research-<YYYY-MM-DD>.md` — this run's report.

Create it: `WORK="./work/market-research"` and `mkdir -p "$WORK"`.

Pick a `RUN_ID` for this run that encodes the chosen angles (e.g.
`2026-06-22-games-br`); it is stored with each suggestion so future runs can see
which angles were used recently.

## Phase 0: Seed rotation
Read `${CLAUDE_PLUGIN_ROOT}/skills/market-research/references/research-angles.md`.
If `$WORK/history.json` exists, skim recent `run_id`s to see which angles were
used lately. Choose 2–3 categories, 1–2 regions, and 1 niche lens you did NOT use
last run. If the command passed a focus argument, force one category to match it.
State the chosen angles to the user in one line before continuing.

## Phase 1: Gather (free web)
Hard chart data — for each chosen region, pull the relevant feeds:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-charts.py \
  topfreeapplications --region <region> --limit 25 > "$WORK/charts-<region>-free.json"
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-charts.py \
  topgrossingapplications --region <region> --limit 25 > "$WORK/charts-<region>-grossing.json"
```
(Top-grossing = monetization signal; top-free = demand signal. Add
`toppaidapplications` if willingness-to-pay matters for the angle.) If a fetch
fails, note it and continue with the feeds you got.

Trend signal — use WebSearch for the chosen categories/niches: new releases,
ProductHunt launches, Reddit/news chatter in the last ~90 days, "fastest growing
<category> apps 2026", dated-incumbent complaints. Vary the queries by the
run's angles so two runs don't search the same terms. These results are the
qualitative half the charts can't give.

## Phase 2: Synthesize candidates
Cluster the chart entries + web findings into **at least 12** distinct app/game
ideas (synthesize more than 10 so dedup in Phase 4 still leaves ≥10). For each:
name, category, what-it-does, why-now (trend signal), incumbent(s), monetization
model. Note that App Store `bundle_id`s from the charts are iOS — treat them as
signal, not Android packages. Write the working list as a JSON array (objects
with at least `name`, optional `package`, `category`) to `$WORK/candidates.json`.

## Phase 3: Score
Read `${CLAUDE_PLUGIN_ROOT}/skills/market-research/references/scoring-guide.md`.
Score every candidate's four components and weighted total. Add the subscores and
`total` to each object in `$WORK/candidates.json`. Rank by `total` descending.

## Phase 4: History dedup
Drop anything already suggested:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/history.py \
  filter --history "$WORK/history.json" < "$WORK/candidates.json" > "$WORK/fresh.json"
```
If fewer than 10 candidates survive, go back to Phase 1/2 with a different angle
and synthesize more, then re-filter — never present a padded or repeated list.

## Phase 5: Present + handoff
Read `${CLAUDE_PLUGIN_ROOT}/skills/market-research/references/report-template.md`.
Fill it from `$WORK/fresh.json` and write `$WORK/research-<YYYY-MM-DD>.md` (use
the actual run date). Show the user the ranked table (≥10 rows) and your top-3
recommended picks.

Record this run's suggestions so they won't repeat:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/history.py \
  add --history "$WORK/history.json" --date <YYYY-MM-DD> --run-id "<RUN_ID>" \
  < "$WORK/fresh.json"
```

Then ask which candidate(s) to pursue. For each pick:
1. Resolve it to a Google Play package/URL. If you don't already have the package,
   WebSearch `"<name>" site:play.google.com` (or the developer + app name) and
   confirm the `play.google.com/store/apps/details?id=...` URL.
2. Invoke the `clone-app` skill on that URL/package to run full feasibility.
If the user picks nothing, stop — the report stands on its own.

## Error Handling Summary
| Scenario | Action |
|---|---|
| `fetch-charts.py` fails for a region | note it, continue with other feeds/web search |
| Web search returns thin results | broaden queries within the chosen angle, try another region |
| < 10 candidates survive dedup | loop back to Phase 1/2 with a new angle, re-filter |
| history.json missing/first run | treat as empty; all candidates are fresh |
| Candidate has no resolvable Play package | skip the handoff for it, keep it in the report as iOS-only/unresolved |
| User picks nothing | stop after writing the report |
```

- [ ] **Step 4: Run the content test to verify it passes**

Run: `bash plugins/market-research/tests/test-skill-content.sh`
Expected: every line `PASS`, exit 0.

- [ ] **Step 5: Run the structural smoke test (now fully green)**

Run: `bash plugins/market-research/tests/smoke-structure.sh`
Expected: every line `PASS`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/market-research/skills/market-research/SKILL.md \
        plugins/market-research/tests/test-skill-content.sh
git commit -m "feat(market-research): add 6-phase SKILL.md orchestrator with clone-app handoff"
```

---

### Task 6: Test aggregator + full-suite green

Add the `run-all.sh` aggregator (mirroring clone-app's) so the whole plugin tests with one command, and confirm everything passes together with the upstream tree still untouched.

**Files:**
- Create: `plugins/market-research/tests/run-all.sh`

**Interfaces:**
- Consumes: every `test-*.sh` and `test-*.py` plus `smoke-structure.sh` from Tasks 1–5.
- Produces: `bash plugins/market-research/tests/run-all.sh` → runs the suite, prints `ALL TESTS PASSED` / `SOME TESTS FAILED`, exits non-zero on any failure.

- [ ] **Step 1: Write the aggregator**

Create `plugins/market-research/tests/run-all.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
fail=0

echo "=== structure ==="
bash "$HERE/smoke-structure.sh" || fail=1

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

- [ ] **Step 2: Make it executable and run the full suite**

Run:
```bash
chmod +x plugins/market-research/tests/run-all.sh
bash plugins/market-research/tests/run-all.sh
```
Expected: ends with `ALL TESTS PASSED`, exit 0.

- [ ] **Step 3: Verify the upstream tree is still byte-identical**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: prints **nothing**.

- [ ] **Step 4: Verify both manifests are valid JSON**

Run:
```bash
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); json.load(open('plugins/market-research/.claude-plugin/plugin.json')); print('JSON OK')"
```
Expected: `JSON OK`.

- [ ] **Step 5: Commit**

```bash
git add plugins/market-research/tests/run-all.sh
git commit -m "test(market-research): add run-all.sh suite aggregator"
```

---

## Self-Review

**1. Spec coverage** (against §6 of the design spec):
- P0 seed rotation → Task 4 `research-angles.md` + Task 5 SKILL Phase 0. ✓
- P1 gather (App Store RSS + web) → Task 2 `fetch-charts.py` + SKILL Phase 1. ✓
- P2 synthesize ≥10 → SKILL Phase 2 (synthesize ≥12 to survive dedup). ✓
- P3 composite score → Task 4 `scoring-guide.md` + SKILL Phase 3. ✓
- P4 history dedup → Task 3 `history.py` + SKILL Phase 4. ✓
- P5 present + clone-app handoff incl. package resolution → SKILL Phase 5. ✓
- State files (`history.json`, `research-<date>.md`) → Task 3 + SKILL state section. ✓
- Scripts stdlib-only, offline-fixture tested → Tasks 2,3. ✓
- Three rubrics → Task 4. ✓
- Tests (fixtures, dedup, scoring sanity via scoring-guide, smoke) → Tasks 1,2,3,5,6. ✓
- Marketplace entry, own plugin.json → Task 1. ✓
- Upstream untouched → checked in Tasks 1,6. ✓

Note: the spec mentioned a "scoring sanity" test; scoring is an AI-judgment step driven by `scoring-guide.md` (a rubric, not code), so it is validated by the SKILL content test referencing the rubric rather than a unit test — consistent with clone-app, where rubric-driven steps have no unit test.

**2. Placeholder scan:** No "TBD"/"TODO"/"handle edge cases" left. All code blocks are complete and runnable. Error handling is concrete (explicit fallbacks in scripts and the SKILL Error Handling table).

**3. Type consistency:** `cand_key` defined once (Task 3) and referenced by name in Task 5; candidate object shape (`name`, optional `package`, `category`, subscores, `total`) is consistent across Tasks 3, 4, 5. `fetch-charts.py` output keys (`feed`,`region`,`count`,`entries[]` with `rank`/`name`/`developer`/`category`/`bundle_id`/`price`) match between Task 2 implementation and test. `history.py` subcommands (`filter`/`add`, `--history`/`--date`/`--run-id`) match between Task 3 impl, test, and SKILL Phase 4/5 calls.
