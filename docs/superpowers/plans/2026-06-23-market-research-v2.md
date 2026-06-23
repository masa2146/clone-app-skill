# Market Research v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the `market-research` skill to produce numerically-grounded, source-cited clone candidates that each carry 1–2 verified Google Play Store links — all free, no API keys.

**Architecture:** Add three deterministic scraper scripts (AppBrain Play charts, a Play resolver/saturation tool, a best-effort Google Trends fetcher) plus a curated numeric-sources rubric. Rewrite the scoring guide to require numeric evidence, the report template to carry Play links + citations + saturation, and the SKILL orchestrator to a survivor-only-enrichment phase flow. Each scraper is fixture-tested offline; reality is confirmed by a one-time live-fetch validation step.

**Tech Stack:** Python 3 stdlib only (`urllib`, `json`, `re`, `subprocess`/`curl` SSL fallback), bash 4+, Markdown skill/reference docs.

## Global Constraints

- **Free, no API key, no pip, no virtualenv.** Python stdlib only.
- **bash 4+ at runtime;** every script `#!/usr/bin/env bash` or `#!/usr/bin/env python3`. Invoke bash scripts with `bash <path>`.
- **`plugins/android-reverse-engineering/` stays byte-identical.** `git status --porcelain plugins/android-reverse-engineering/` must print nothing. All work confined to `plugins/market-research/`.
- **Scrape logic is tested offline against `tests/fixtures/`** via a `--html-file` / `--json-file` flag — never a live network call in a test.
- **Working dir is `./work/market-research/`** in the user's cwd, never inside the plugin.
- New Python scripts mirror `fetch-charts.py`: `UA = "Mozilla/5.0"`, a `_http_get` with urllib→`curl` SSL fallback, `--*-file` offline flag, `ERROR: …` to stderr + `sys.exit(1)` on fetch failure, `json.dumps(..., indent=2)` to stdout.
- Bash tests use `set -uo pipefail` (not `-e`) and aggregate failures into a `fail` var.
- Commits follow Conventional Commits scoped to the plugin: `feat(market-research): …`, `test(market-research): …`, `docs(market-research): …`.
- Scripts must be committed executable (`chmod +x`).
- Branch: `feat/market-research-v2` (already created).

---

## File Structure

**Create:**
- `plugins/market-research/skills/market-research/scripts/fetch-play-charts.py` — AppBrain HTML top-charts → normalized JSON (real Android packages).
- `plugins/market-research/skills/market-research/scripts/play.py` — `resolve` (name → Play URL + stats) and `count` (saturation) subcommands.
- `plugins/market-research/skills/market-research/scripts/trends.py` — best-effort Google Trends, never hard-fails.
- `plugins/market-research/skills/market-research/references/numeric-sources.md` — curated free numeric-data sources + query/extraction rubric.
- `plugins/market-research/tests/test-fetch-play-charts.py`
- `plugins/market-research/tests/test-play.py`
- `plugins/market-research/tests/test-trends.py`
- `plugins/market-research/tests/fixtures/appbrain-popular.html`
- `plugins/market-research/tests/fixtures/play-search.html`
- `plugins/market-research/tests/fixtures/play-details.html`
- `plugins/market-research/tests/fixtures/trends-sample.json`

**Modify (rewrite):**
- `plugins/market-research/skills/market-research/references/scoring-guide.md` — numeric scoring + evidence.
- `plugins/market-research/skills/market-research/references/report-template.md` — Play links, citations, saturation.
- `plugins/market-research/skills/market-research/SKILL.md` — new phase flow (0–7).

**Modify (extend):**
- `plugins/market-research/tests/smoke-structure.sh` — assert new scripts/refs exist + executable.
- `plugins/market-research/README.md` — document new scripts/flow.

`run-all.sh` needs no change — it globs `test-*.py` / `test-*.sh`.

---

## Task 1: AppBrain Play charts scraper

**Files:**
- Create: `plugins/market-research/skills/market-research/scripts/fetch-play-charts.py`
- Create: `plugins/market-research/tests/fixtures/appbrain-popular.html`
- Test: `plugins/market-research/tests/test-fetch-play-charts.py`

**Interfaces:**
- Consumes: nothing.
- Produces: CLI `fetch-play-charts.py <chart> [--region R] [--limit N] [--html-file F]` where `<chart> ∈ {popular, top-grossing, top-new}`. Stdout JSON: `{"source":"appbrain","chart":str,"region":str,"count":int,"entries":[{"rank":int,"name":str,"developer":str|None,"category":str|None,"package":str,"rating":float|None,"installs":str|None}]}`.

- [ ] **Step 1: Create the synthetic fixture**

Create `plugins/market-research/tests/fixtures/appbrain-popular.html` with markup matching AppBrain's app-list rows (a link to `/app/<slug>/<package>` carrying name, developer, rating, installs):

```html
<!DOCTYPE html><html><body>
<div class="app-list">
  <div class="app">
    <a class="app-icon-name" href="/app/habit-tracker/com.example.habit">Habit Tracker</a>
    <span class="developer">Focus Labs</span>
    <span class="category">Productivity</span>
    <span class="rating">4.6</span>
    <span class="installs">5,000,000+</span>
  </div>
  <div class="app">
    <a class="app-icon-name" href="/app/budget-buddy/com.example.budget">Budget Buddy</a>
    <span class="developer">Money Inc</span>
    <span class="category">Finance</span>
    <span class="rating">4.2</span>
    <span class="installs">1,000,000+</span>
  </div>
</div>
</body></html>
```

- [ ] **Step 2: Write the failing test**

Create `plugins/market-research/tests/test-fetch-play-charts.py`:

```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "fetch-play-charts.py")
FIXTURE = os.path.join(HERE, "fixtures", "appbrain-popular.html")

def run():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "popular", "--region", "us", "--html-file", FIXTURE])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    check("source", d["source"] == "appbrain")
    check("chart", d["chart"] == "popular")
    check("count", d["count"] == 2)
    e0 = d["entries"][0]
    check("rank 1", e0["rank"] == 1)
    check("name", e0["name"] == "Habit Tracker")
    check("package", e0["package"] == "com.example.habit")
    check("developer", e0["developer"] == "Focus Labs")
    check("category", e0["category"] == "Productivity")
    check("rating", e0["rating"] == 4.6)
    check("installs", e0["installs"] == "5,000,000+")
    for k in ["rank", "name", "package", "developer", "category", "rating", "installs"]:
        check(f"key present: {k}", k in e0)
    check("second package", d["entries"][1]["package"] == "com.example.budget")
    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run test, verify it fails**

Run: `python3 plugins/market-research/tests/test-fetch-play-charts.py`
Expected: FAIL — script does not exist (`No such file` / non-zero exit).

- [ ] **Step 4: Write the script**

Create `plugins/market-research/skills/market-research/scripts/fetch-play-charts.py`:

```python
#!/usr/bin/env python3
"""Fetch an AppBrain Play-store top-chart into a normalized JSON list.

Google Play has no public chart feed and renders via obfuscated batchexecute
JS. AppBrain (appbrain.com) publishes server-rendered HTML top-chart pages with
REAL Android package names. This scrapes those rows. Stdlib-only, no pip.

Unlike Apple's RSS (iOS bundle ids), entries here carry Android packages usable
directly for a clone-app handoff.
"""
import sys, json, re, argparse, urllib.request, ssl, subprocess, shutil

CHARTS = {
    "popular": "https://www.appbrain.com/apps/popular/",
    "top-grossing": "https://www.appbrain.com/apps/highest-grossing/",
    "top-new": "https://www.appbrain.com/apps/new/",
}
UA = "Mozilla/5.0"

def _http_get(url):
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

# One app row: a link to /app/<slug>/<package> followed (within the same row
# block) by developer / category / rating / installs spans.
ROW = re.compile(
    r'href="/app/[^"/]+/(?P<package>[\w.]+)"[^>]*>(?P<name>[^<]+)</a>'
    r'(?P<rest>.*?)(?=href="/app/|</div>\s*</div>|$)', re.DOTALL)
DEV = re.compile(r'class="developer"[^>]*>([^<]+)<')
CAT = re.compile(r'class="category"[^>]*>([^<]+)<')
RAT = re.compile(r'class="rating"[^>]*>\s*([\d.]+)\s*<')
INST = re.compile(r'class="installs"[^>]*>\s*([\d,]+\+)\s*<')

def _first(rx, text):
    m = rx.search(text)
    return m.group(1).strip() if m else None

def parse(html, chart, region, limit):
    entries = []
    for i, m in enumerate(ROW.finditer(html), start=1):
        if i > limit:
            break
        rest = m.group("rest")
        rating = _first(RAT, rest)
        entries.append({
            "rank": i,
            "name": m.group("name").strip(),
            "developer": _first(DEV, rest),
            "category": _first(CAT, rest),
            "package": m.group("package"),
            "rating": float(rating) if rating else None,
            "installs": _first(INST, rest),
        })
    return {"source": "appbrain", "chart": chart, "region": region,
            "count": len(entries), "entries": entries}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chart", choices=sorted(CHARTS))
    ap.add_argument("--region", default="us")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--html-file")
    args = ap.parse_args()

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()
    else:
        try:
            html = _http_get(CHARTS[args.chart])
        except Exception as e:
            print(f"ERROR: failed to fetch AppBrain chart: {e}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps(parse(html, args.chart, args.region, args.limit), indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Make it executable**

Run: `chmod +x plugins/market-research/skills/market-research/scripts/fetch-play-charts.py`

- [ ] **Step 6: Run test, verify it passes**

Run: `python3 plugins/market-research/tests/test-fetch-play-charts.py`
Expected: every line `PASS`, exit 0.

- [ ] **Step 7: Validate the selectors against live AppBrain once**

Run: `python3 plugins/market-research/skills/market-research/scripts/fetch-play-charts.py popular --limit 5`
Expected: JSON with ~5 entries carrying real `com.*` packages. **If the live markup differs from the fixture** (empty `entries`), update both the regexes in the script AND `appbrain-popular.html` to match the real structure, then re-run Step 6 until the offline test passes against the corrected fixture. If AppBrain blocks/changes hosting, record the failure in the commit message and keep the script (the skill degrades to Apple RSS + web).

- [ ] **Step 8: Commit**

```bash
git add plugins/market-research/skills/market-research/scripts/fetch-play-charts.py \
        plugins/market-research/tests/test-fetch-play-charts.py \
        plugins/market-research/tests/fixtures/appbrain-popular.html
git commit -m "feat(market-research): add AppBrain Play-charts scraper"
```

---

## Task 2: Play resolver (`play.py resolve`)

**Files:**
- Create: `plugins/market-research/skills/market-research/scripts/play.py`
- Create: `plugins/market-research/tests/fixtures/play-search.html`
- Create: `plugins/market-research/tests/fixtures/play-details.html`
- Test: `plugins/market-research/tests/test-play.py`

**Interfaces:**
- Consumes: nothing.
- Produces: CLI `play.py resolve "<name>" [--search-file F] [--details-file F]`. Stdout JSON: `{"query":str,"name":str|None,"package":str|None,"play_url":str|None,"rating":float|None,"installs":str|None,"last_updated":str|None,"developer":str|None}`. When no app is found: same keys, `package`/`play_url` `None`. `--search-file`/`--details-file` feed offline HTML (no network).

- [ ] **Step 1: Create the search fixture**

Create `plugins/market-research/tests/fixtures/play-search.html` (Play search results carry `href="/store/apps/details?id=PKG"` plus star aria-labels):

```html
<!DOCTYPE html><html><body>
<div role="main">
  <a href="/store/apps/details?id=com.example.habit"><span>Habit Tracker</span></a>
  <div aria-label="Rated 4.6 stars out of five stars"></div>
  <a href="/store/apps/details?id=com.example.habit2"><span>Habit Plus</span></a>
  <div aria-label="Rated 4.1 stars out of five stars"></div>
  <a href="/store/apps/details?id=com.example.habit3"><span>Daily Habits</span></a>
  <div aria-label="Rated 3.9 stars out of five stars"></div>
</div>
</body></html>
```

- [ ] **Step 2: Create the details fixture**

Create `plugins/market-research/tests/fixtures/play-details.html` matching the `ld+json` + installs/updated structure clone-app already parses:

```html
<!DOCTYPE html><html><body>
<script type="application/ld+json" nonce="abc">
{"@type":"SoftwareApplication","name":"Habit Tracker","author":{"name":"Focus Labs"},
"applicationCategory":"Productivity","aggregateRating":{"ratingValue":"4.6","ratingCount":"120000"}}
</script>
<div>5,000,000+</div><div>Downloads</div>
<div>Updated on</div><div>Jun 1, 2026</div>
</body></html>
```

- [ ] **Step 3: Write the failing test**

Create `plugins/market-research/tests/test-play.py`:

```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "play.py")
SEARCH = os.path.join(HERE, "fixtures", "play-search.html")
DETAILS = os.path.join(HERE, "fixtures", "play-details.html")

def run(*args):
    return json.loads(subprocess.check_output([sys.executable, SCRIPT, *args]))

def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    r = run("resolve", "Habit Tracker", "--search-file", SEARCH, "--details-file", DETAILS)
    check("package", r["package"] == "com.example.habit")
    check("play_url", r["play_url"] == "https://play.google.com/store/apps/details?id=com.example.habit")
    check("name", r["name"] == "Habit Tracker")
    check("rating", r["rating"] == 4.6)
    check("installs", r["installs"] == "5,000,000+")
    check("last_updated", r["last_updated"] == "Jun 1, 2026")
    check("developer", r["developer"] == "Focus Labs")

    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 4: Run test, verify it fails**

Run: `python3 plugins/market-research/tests/test-play.py`
Expected: FAIL — `play.py` does not exist.

- [ ] **Step 5: Write `play.py` (resolve only for now)**

Create `plugins/market-research/skills/market-research/scripts/play.py`:

```python
#!/usr/bin/env python3
"""Resolve an app name to a Google Play link + stats, and measure saturation.

Subcommands:
  resolve "<name>"  -> top Play apps hit: package, play_url, rating, installs,
                       last_updated, developer (1-2 links per candidate upstream).
  count   "<query>" -> saturation: how many distinct apps + avg rating on the
                       first Play search results page.

Play search (play.google.com/store/search?q=...&c=apps&hl=en&gl=US) is
server-rendered enough to grep details?id= links + star aria-labels. The details
page carries rating/installs/updated in embedded ld+json (+ light regex), the
same structure clone-app's scrape-play-store.py parses. Stdlib-only, no pip.
"""
import sys, json, re, argparse, urllib.request, ssl, subprocess, shutil

UA = "Mozilla/5.0"
ID_RE = re.compile(r'/store/apps/details\?id=([\w.]+)')
STAR_RE = re.compile(r'Rated\s+([\d.]+)\s+stars')

def _http_get(url):
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

def _search_html(query, search_file):
    if search_file:
        with open(search_file, encoding="utf-8") as f:
            return f.read()
    q = urllib.parse.quote(query)
    return _http_get(f"https://play.google.com/store/search?q={q}&c=apps&hl=en&gl=US")

def _details_html(package, details_file):
    if details_file:
        with open(details_file, encoding="utf-8") as f:
            return f.read()
    return _http_get(
        f"https://play.google.com/store/apps/details?id={package}&hl=en&gl=US")

def parse_details(html, package):
    out = {"name": None, "developer": None, "rating": None,
           "installs": None, "last_updated": None}
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                         html, re.DOTALL):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "SoftwareApplication":
            out["name"] = data.get("name")
            auth = data.get("author")
            if isinstance(auth, dict):
                out["developer"] = auth.get("name")
            ar = data.get("aggregateRating") or {}
            if ar.get("ratingValue") is not None:
                try: out["rating"] = float(ar["ratingValue"])
                except Exception: pass
            break
    m = re.search(r'([\d,]+\+)\s*</[^>]+>\s*<[^>]*>\s*Downloads', html)
    if not m:
        m = re.search(r'([\d,]+\+)\s*<span>\s*Downloads', html)
    if m:
        out["installs"] = m.group(1)
    m = re.search(r'Updated on\s*</[^>]+>\s*<[^>]*>([^<]+)</[^>]+>', html)
    if not m:
        m = re.search(r'Updated on\s*<span>([^<]+)</span>', html)
    if m:
        out["last_updated"] = m.group(1).strip()
    return out

def cmd_resolve(args):
    html = _search_html(args.query, args.search_file)
    m = ID_RE.search(html)
    res = {"query": args.query, "name": None, "package": None, "play_url": None,
           "rating": None, "installs": None, "last_updated": None, "developer": None}
    if not m:
        print(json.dumps(res, indent=2))
        return
    package = m.group(1)
    res["package"] = package
    res["play_url"] = f"https://play.google.com/store/apps/details?id={package}"
    details = _details_html(package, args.details_file)
    res.update(parse_details(details, package))
    print(json.dumps(res, indent=2))

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("resolve")
    pr.add_argument("query")
    pr.add_argument("--search-file")
    pr.add_argument("--details-file")
    args = ap.parse_args()
    if args.cmd == "resolve":
        try:
            cmd_resolve(args)
        except Exception as e:
            print(f"ERROR: play resolve failed: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used by _search_html)
    main()
```

> Note: move `import urllib.parse` to the top with the other imports if you prefer; it must be imported before `_search_html` runs.

- [ ] **Step 6: Make it executable**

Run: `chmod +x plugins/market-research/skills/market-research/scripts/play.py`

- [ ] **Step 7: Run test, verify resolve passes**

Run: `python3 plugins/market-research/tests/test-play.py`
Expected: every line `PASS`, exit 0.

- [ ] **Step 8: Validate against live Play once**

Run: `python3 plugins/market-research/skills/market-research/scripts/play.py resolve "habit tracker"`
Expected: JSON with a real `com.*` package + `play_url` + rating/installs. **If `package` is null** (Play markup changed), inspect the live search HTML, fix `ID_RE`/`parse_details` and the fixtures to match, re-run Step 7. Record any live-blocking in the commit message.

- [ ] **Step 9: Commit**

```bash
git add plugins/market-research/skills/market-research/scripts/play.py \
        plugins/market-research/tests/test-play.py \
        plugins/market-research/tests/fixtures/play-search.html \
        plugins/market-research/tests/fixtures/play-details.html
git commit -m "feat(market-research): add play.py resolve (name -> Play link + stats)"
```

---

## Task 3: Play saturation (`play.py count`)

**Files:**
- Modify: `plugins/market-research/skills/market-research/scripts/play.py` (add `count` subcommand)
- Modify: `plugins/market-research/tests/test-play.py` (add count assertions)

**Interfaces:**
- Consumes: the `play-search.html` fixture + `STAR_RE`/`ID_RE` from Task 2.
- Produces: CLI `play.py count "<query>" [--search-file F]`. Stdout JSON: `{"query":str,"app_count":int,"avg_rating":float|None,"top_packages":[str,...]}`. `app_count` = distinct `details?id=` packages on the first results page; `avg_rating` = mean of star aria-labels rounded to 2 dp.

- [ ] **Step 1: Add the failing test assertions**

Append to `main()` in `plugins/market-research/tests/test-play.py`, before `sys.exit(...)`:

```python
    c = run("count", "habit tracker", "--search-file", SEARCH)
    check("app_count", c["app_count"] == 3)
    check("avg_rating", c["avg_rating"] == 4.2)  # mean(4.6,4.1,3.9)=4.2
    check("top_packages has habit", "com.example.habit" in c["top_packages"])
    check("top_packages distinct", len(c["top_packages"]) == len(set(c["top_packages"])))
```

- [ ] **Step 2: Run test, verify the new assertions fail**

Run: `python3 plugins/market-research/tests/test-play.py`
Expected: the `app_count` / `avg_rating` lines FAIL (subparser `count` missing → non-zero exit), resolve lines still PASS.

- [ ] **Step 3: Add the `count` subcommand to `play.py`**

Add this function above `main()`:

```python
def cmd_count(args):
    html = _search_html(args.query, args.search_file)
    packages = []
    for pkg in ID_RE.findall(html):
        if pkg not in packages:
            packages.append(pkg)
    ratings = [float(x) for x in STAR_RE.findall(html)]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else None
    print(json.dumps({"query": args.query, "app_count": len(packages),
                      "avg_rating": avg, "top_packages": packages}, indent=2))
```

In `main()`, register the subparser and dispatch:

```python
    pc = sub.add_parser("count")
    pc.add_argument("query")
    pc.add_argument("--search-file")
```

and replace the dispatch tail with:

```python
    try:
        {"resolve": cmd_resolve, "count": cmd_count}[args.cmd](args)
    except Exception as e:
        print(f"ERROR: play {args.cmd} failed: {e}", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 4: Run test, verify all pass**

Run: `python3 plugins/market-research/tests/test-play.py`
Expected: every line `PASS`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add plugins/market-research/skills/market-research/scripts/play.py \
        plugins/market-research/tests/test-play.py
git commit -m "feat(market-research): add play.py count (saturation density)"
```

---

## Task 4: Best-effort Google Trends fetcher

**Files:**
- Create: `plugins/market-research/skills/market-research/scripts/trends.py`
- Create: `plugins/market-research/tests/fixtures/trends-sample.json`
- Test: `plugins/market-research/tests/test-trends.py`

**Interfaces:**
- Consumes: nothing.
- Produces: CLI `trends.py "<term>" [--json-file F]`. On success (or `--json-file`): `{"ok":true,"term":str,"avg_interest":float,"latest_interest":int,"trend_pct":float|None,"points":int}`. On any live failure: exit 0 with `{"ok":false,"term":str,"fallback":"websearch"}` — **never hard-fails** so the skill can fall back to WebSearch. `--json-file` parses a saved Trends `multiline` JSON (the `default.timelineData` shape) offline.

- [ ] **Step 1: Create the fixture**

Create `plugins/market-research/tests/fixtures/trends-sample.json` (the shape Google Trends' `multiline` endpoint returns after the `)]}',` prefix is stripped):

```json
{"default":{"timelineData":[
  {"time":"1","value":[50]},
  {"time":"2","value":[60]},
  {"time":"3","value":[100]}
]}}
```

- [ ] **Step 2: Write the failing test**

Create `plugins/market-research/tests/test-trends.py`:

```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "trends.py")
FIXTURE = os.path.join(HERE, "fixtures", "trends-sample.json")

def run(*args):
    # exit 0 always (never hard-fails); capture stdout
    out = subprocess.run([sys.executable, SCRIPT, *args],
                         capture_output=True, text=True)
    return out.returncode, json.loads(out.stdout)

def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    rc, d = run("habit tracker", "--json-file", FIXTURE)
    check("exit 0", rc == 0)
    check("ok", d["ok"] is True)
    check("points", d["points"] == 3)
    check("latest_interest", d["latest_interest"] == 100)
    check("avg_interest", d["avg_interest"] == 70.0)  # mean(50,60,100)=70
    check("trend_pct", d["trend_pct"] == 100.0)        # (100-50)/50*100

    # bad fixture -> graceful fallback, still exit 0
    rc2, d2 = run("x", "--json-file", os.path.join(HERE, "fixtures", "appbrain-popular.html"))
    check("fallback exit 0", rc2 == 0)
    check("fallback ok false", d2["ok"] is False)
    check("fallback flag", d2["fallback"] == "websearch")

    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run test, verify it fails**

Run: `python3 plugins/market-research/tests/test-trends.py`
Expected: FAIL — `trends.py` does not exist.

- [ ] **Step 4: Write `trends.py`**

Create `plugins/market-research/skills/market-research/scripts/trends.py`:

```python
#!/usr/bin/env python3
"""Best-effort Google Trends interest signal. NEVER hard-fails.

Google Trends has no API key but the unofficial endpoint needs a token dance
and is fragile under stdlib-only. So: try the live token+timeline flow; on ANY
failure print {"ok": false, "fallback": "websearch"} and exit 0, signalling the
skill to fall back to WebSearch for the same momentum signal. The JSON parser is
unit-tested offline via --json-file. Stdlib-only, no pip.
"""
import sys, json, argparse, urllib.request, urllib.parse, ssl, subprocess, shutil

UA = "Mozilla/5.0"

def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
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

def parse_timeline(raw):
    """raw = the timeline JSON (Google prefixes live responses with )]}',  —
    callers strip it first). Returns the computed interest summary dict."""
    data = json.loads(raw)
    points = data["default"]["timelineData"]
    values = [int(p["value"][0]) for p in points if p.get("value")]
    if not values:
        raise ValueError("no timeline values")
    avg = round(sum(values) / len(values), 2)
    first, latest = values[0], values[-1]
    pct = round((latest - first) / first * 100, 2) if first else None
    return {"ok": True, "avg_interest": avg, "latest_interest": latest,
            "trend_pct": pct, "points": len(values)}

def fetch_live(term):
    """Token dance: explore -> widget token -> multiline timeline."""
    base = "https://trends.google.com/trends/api"
    comp = urllib.parse.quote(json.dumps(
        {"comparisonItem": [{"keyword": term, "geo": "", "time": "today 3-m"}],
         "category": 0, "property": ""}))
    explore = _http_get(f"{base}/explore?hl=en-US&tz=0&req={comp}")
    widgets = json.loads(explore.lstrip(")]}',\n"))
    w = next(x for x in widgets["widgets"] if x.get("id") == "TIMESERIES")
    token = w["token"]
    reqobj = urllib.parse.quote(json.dumps(w["request"]))
    tl = _http_get(f"{base}/widgetdata/multiline?hl=en-US&tz=0&req={reqobj}&token={token}")
    return tl.lstrip(")]}',\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("term")
    ap.add_argument("--json-file")
    args = ap.parse_args()

    try:
        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                raw = f.read()
        else:
            raw = fetch_live(args.term)
        res = parse_timeline(raw)
        res["term"] = args.term
        print(json.dumps(res, indent=2))
    except Exception:
        print(json.dumps({"ok": False, "term": args.term,
                          "fallback": "websearch"}, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Make it executable**

Run: `chmod +x plugins/market-research/skills/market-research/scripts/trends.py`

- [ ] **Step 6: Run test, verify it passes**

Run: `python3 plugins/market-research/tests/test-trends.py`
Expected: every line `PASS`, exit 0.

- [ ] **Step 7: Smoke the live path (informational, may fall back)**

Run: `python3 plugins/market-research/skills/market-research/scripts/trends.py "habit tracker"`
Expected: either `{"ok": true, ...}` with numbers, OR `{"ok": false, "fallback": "websearch"}`. Both are acceptable (best-effort). Exit code must be 0 either way.

- [ ] **Step 8: Commit**

```bash
git add plugins/market-research/skills/market-research/scripts/trends.py \
        plugins/market-research/tests/test-trends.py \
        plugins/market-research/tests/fixtures/trends-sample.json
git commit -m "feat(market-research): add best-effort Google Trends fetcher"
```

---

## Task 5: Numeric-sources reference rubric

**Files:**
- Create: `plugins/market-research/skills/market-research/references/numeric-sources.md`

**Interfaces:**
- Consumes: nothing (a prose rubric).
- Produces: a reference the SKILL's Phase 2 reads to drive WebSearch/WebFetch at named numeric sources and extract specific numbers with citations.

- [ ] **Step 1: Write the reference**

Create `plugins/market-research/skills/market-research/references/numeric-sources.md`:

```markdown
# Numeric Market-Data Sources (free, no API key)

Phase 2 uses this to turn "search the web" into "pull THESE numbers from THESE
places, and cite each." Prefer a real number with a source link over a vibe.
Every number that lands in the report carries the URL it came from.

## Sources & what to pull

| Source | Pull | How (free) |
|---|---|---|
| **Google Trends** | interest-over-time, % momentum, breakout/rising queries | `trends.py "<term>"`; on `{"ok":false}` fall back to WebSearch `google trends <term>`. |
| **AppBrain** | install brackets, category rank/share, Android growth | `fetch-play-charts.py` for charts; WebSearch `appbrain <app/category> statistics` for detail pages. |
| **Sensor Tower (blog/reports)** | downloads, revenue, DAU, YoY growth | WebSearch `sensortower <category> revenue downloads 2026`; WebFetch the article; quote the figure + date. |
| **data.ai / Apptopia posts** | top-charts movement, market revenue | WebSearch `data.ai <category> market 2026`; WebFetch + cite. |
| **Statista (free public charts)** | market size $, user counts, CAGR | WebSearch `statista <category> market size`; use the visible free figure only; cite. |
| **SimilarWeb (free tier)** | incumbent web traffic, engagement | WebSearch `similarweb <incumbent domain>`; cite visits/engagement. |

## Query shaping (vary by the run's angles)

- Always bind a year: `... 2026` so figures are current.
- Bind a region when the angle is regional: `... <category> Brazil downloads`.
- For growth: `fastest growing <category> apps 2026`, `<category> market size 2026`.
- For incumbent weakness: `<incumbent> complaints reddit`, `<incumbent> alternative 2026`.

## Citation rule

Each extracted number is written as `<number> [<source>](<url>)` in the report.
A claim with no source link is downgraded to a qualitative note, not a number —
it must NOT be used to justify a numeric subscore (see scoring-guide.md).

## When a source is paywalled / JS-only

Do not scrape it. Use the figure only if it's visible free (article body, public
chart). Otherwise drop to the next source. Never invent a number to fill a gap.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/market-research/skills/market-research/references/numeric-sources.md
git commit -m "docs(market-research): add numeric-sources rubric"
```

---

## Task 6: Rewrite scoring guide for numeric evidence

**Files:**
- Modify (rewrite): `plugins/market-research/skills/market-research/references/scoring-guide.md`

**Interfaces:**
- Consumes: numbers from Tasks 1–5 (installs, trend %, saturation count, source-cited figures).
- Produces: scoring rubric requiring an `evidence` object per candidate; weights unchanged (clone 35 / market 35 / monet 20 / niche 10).

- [ ] **Step 1: Rewrite the file**

Replace the entire contents of `plugins/market-research/skills/market-research/references/scoring-guide.md` with:

```markdown
# Scoring Guide (numeric)

Score every candidate 0–100 as a weighted composite of three PRIMARY components
plus a tiebreaker. **Every subscore must be justified by at least one real number
with a source** (see numeric-sources.md). A subscore with no supporting number is
CAPPED at 60 — you may not assign a high score on vibes.

## Components & weights (unchanged)

| Component | Weight | Measures |
|---|---|---|
| Cloneability | 35% | How cheaply this rebuilds with clone-app + AI. |
| Market opportunity | 35% | Demand, growth, incumbent weakness. |
| Monetization fit | 20% | Ads/IAP friendliness and category ARPU. |
| Niche gap (tiebreaker) | 10% | Underserved region/language/segment. |

`total = 0.35·clone + 0.35·market + 0.20·monetization + 0.10·niche`, each 0–100.

## Required evidence per subscore

Attach an `evidence` object to each candidate. Each field is `"<number> + source"`
or `null`. A field that is `null` caps that subscore at 60.

| Subscore | Evidence that lifts the cap above 60 |
|---|---|
| Cloneability | a stack/complexity signal (e.g. "few endpoints — RE later"); no external number required, but state the basis. |
| Market opportunity | an installs figure (AppBrain/Play) AND either a Trends `trend_pct` OR a saturation `app_count`. |
| Monetization fit | a category ARPU/revenue figure (Sensor Tower/data.ai/Statista) OR top-grossing chart presence. |
| Niche gap | a region/language gap signal (saturation `app_count` low in region, or no localized incumbent). |

## Scoring bands (0–100)

**Cloneability** (higher = easier): 80–100 simple CRUD/utility, few endpoints, no
heavy ML. 50–79 moderate backend/media, mainstream SDKs. 0–49 heavy ML/native/
real-time/large content moat.

**Market opportunity** (higher = better): 80–100 strong/growing demand (high
installs + positive `trend_pct`), weak/dated incumbents, low saturation. 50–79
healthy demand, beatable incumbents, moderate saturation. 0–49 saturated
(`app_count` high, strong avg rating) or entrenched well-funded players.

**Monetization fit** (higher = better): 80–100 proven ads+IAP, high ARPU
(casual games, utilities) with a cited revenue figure. 50–79 monetizable, moderate
ARPU. 0–49 users expect free / hard to monetize.

**Niche gap** (higher = more underserved): 80–100 clear region/language/segment
with no quality option (low regional `app_count`). 0–49 well served everywhere.

## Output per candidate

Keep: `name`, `package` (if resolved), `play_url`(s), `category`, the four
subscores, `evidence` (the cited numbers + source URLs), the weighted `total`,
and a one-line rationale. Rank by `total` descending. Produce ≥10 candidates
AFTER history exclusion.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/market-research/skills/market-research/references/scoring-guide.md
git commit -m "docs(market-research): numeric, evidence-required scoring"
```

---

## Task 7: Rewrite report template for Play links + citations + saturation

**Files:**
- Modify (rewrite): `plugins/market-research/skills/market-research/references/report-template.md`

**Interfaces:**
- Consumes: enriched candidate objects (play_url(s), evidence, saturation, scores).
- Produces: the report shape the SKILL Phase 7 fills.

- [ ] **Step 1: Rewrite the file**

Replace the entire contents of `plugins/market-research/skills/market-research/references/report-template.md` with:

```markdown
# Market Research Report Template

Fill every section. Write to `./work/market-research/research-<YYYY-MM-DD>.md`.
Every number carries a source link. Every candidate carries 1–2 Google Play links.

---

# Market Research — <YYYY-MM-DD>

## Run parameters
- Angles this run: <categories / regions / niche lens chosen in Phase 0>
- Focus argument: <the user's focus, or "none">
- Sources: Apple RSS (<feeds/regions>) + AppBrain Play charts (<charts>) + web numeric (<sources>) + Trends (<ok/fallback>)
- Candidates after history exclusion: <N> (history had <M> prior suggestions)

## Top candidates (ranked)

| # | Name | Category | Play link(s) | Installs | Saturation | Clone | Market | Monet. | Niche | **Total** | Why now (cited) |
|---|------|----------|--------------|---------:|-----------:|------:|-------:|-------:|------:|----------:|-----------------|
| 1 | …    | …        | [Play](url)  | 5M+      | 12 apps/4.2★ | 85 |   80 |   75 |  60 | **79** | trend +120% [src] |

(At least 10 rows. Each Play link is verified live — HTTP 200 + package match.)

## Candidate detail

For each top candidate:

### <name>
- **Play link(s):** [<package1>](url1) [, [<package2>](url2)]  ← 1–2, verified
- **What it does:** <1–2 sentences>
- **Why now:** <trend signal with a number + source link>
- **Incumbents:** <who, and saturation: app_count + avg rating from play.py count>
- **Monetization:** <ads / IAP / subscription; ARPU figure + source>
- **Evidence:** installs <n> [src], trend <pct>% [src], saturation <n> apps, ARPU <…> [src]
- **Scores:** clone <>, market <>, monetization <>, niche <> → **total <>**
- **Clone risk flags:** <heavy ML / native / content moat / none>

## Recommended picks

Top 3 to send to clone-app first, one sentence each on why they lead (cite the
deciding number).

## Next step

The user picks one or more candidates; each chosen candidate already has a
verified Google Play URL and is handed to the `clone-app` skill for full
feasibility. Candidates whose Play link could not be verified are flagged
"Play link unresolved" and skipped on handoff.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/market-research/skills/market-research/references/report-template.md
git commit -m "docs(market-research): report template with Play links, citations, saturation"
```

---

## Task 8: Rewrite SKILL.md orchestrator (new phase flow)

**Files:**
- Modify (rewrite): `plugins/market-research/skills/market-research/SKILL.md`

**Interfaces:**
- Consumes: all scripts (Tasks 1–4) + references (Tasks 5–7).
- Produces: the 8-phase (0–7) prose workflow Claude executes; survivor-only enrichment.

- [ ] **Step 1: Rewrite phases 1–7 (keep the frontmatter, legal note, state/dir, Phase 0)**

In `plugins/market-research/skills/market-research/SKILL.md`, keep lines through Phase 0 unchanged. Replace everything from `## Phase 1:` to end-of-file with:

```markdown
## Phase 1: Gather charts (free)
For each chosen region pull BOTH stores. Apple RSS (iOS signal — bundle ids, not
Android packages):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-charts.py \
  topfreeapplications --region <region> --limit 25 > "$WORK/charts-<region>-free.json"
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-charts.py \
  topgrossingapplications --region <region> --limit 25 > "$WORK/charts-<region>-grossing.json"
```
AppBrain Play charts (Android signal — REAL packages):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-play-charts.py \
  popular --limit 25 > "$WORK/play-popular.json"
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-play-charts.py \
  top-grossing --limit 25 > "$WORK/play-grossing.json"
```
If any fetch fails, note it and continue with the feeds you got.

## Phase 2: Trend + numeric signal
Read `${CLAUDE_PLUGIN_ROOT}/skills/market-research/references/numeric-sources.md`.
For the chosen categories/niches, WebSearch the named numeric sources and pull
real figures (market size, downloads, revenue, YoY) WITH their source URLs. For
the top themes, attempt Trends momentum:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/trends.py "<theme>"
```
If a `trends.py` result is `{"ok": false, "fallback": "websearch"}`, WebSearch the
same momentum signal instead. Vary queries by the run's angles.

## Phase 3: Synthesize ≥12 candidates
Cluster chart entries (Apple + AppBrain) + web findings into ≥12 distinct ideas
(synthesize > 10 so dedup still leaves ≥10). For each: name, category,
what-it-does, why-now (with a cited number where available), incumbent(s),
monetization model. AppBrain entries already give an Android `package`; carry it.
Write the working list as a JSON array (objects with at least `name`, optional
`package`, `category`) to `$WORK/candidates.json`.

## Phase 4: Cheap score + history dedup
Score each candidate on the chart/trend signal you ALREADY have (don't enrich
yet — that's Phase 5). Then drop anything suggested before:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/history.py \
  filter --history "$WORK/history.json" < "$WORK/candidates.json" > "$WORK/fresh.json"
```
If fewer than 10 survive, loop back to Phase 1/2 with a DIFFERENT angle and
synthesize more, then re-filter. Never present a padded or repeated list.

## Phase 5: Enrich survivors only (efficiency)
For the surviving top ~10 ONLY (never the full raw set), enrich each:
1. Resolve 1–2 Play links + stats:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/play.py \
     resolve "<candidate name>"
   ```
2. **Verify** each resolved `play_url` with WebFetch — confirm HTTP 200 and the
   `id=<package>` is present on the page. Drop dead/mismatched links. A candidate
   with no verifiable link is flagged "Play link unresolved" (kept in report,
   skipped on handoff).
3. Saturation:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/play.py \
     count "<category or core feature>"
   ```
4. Momentum (`trends.py` as in Phase 2) if not already pulled.

## Phase 6: Re-score with numbers
Read `${CLAUDE_PLUGIN_ROOT}/skills/market-research/references/scoring-guide.md`.
Re-score every surviving candidate using the enriched numbers; attach the
`evidence` object (cited installs / trend % / saturation / ARPU). Rank by `total`
descending. Subscores with no supporting number are capped per the guide.

## Phase 7: Present + handoff
Read `${CLAUDE_PLUGIN_ROOT}/skills/market-research/references/report-template.md`.
Fill it from the enriched, re-scored survivors and write
`$WORK/research-<YYYY-MM-DD>.md`. Show the user the ranked table (≥10 rows, with
Play links + saturation) and your top-3 picks.

Record this run's suggestions so they won't repeat:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/history.py \
  add --history "$WORK/history.json" --date <YYYY-MM-DD> --run-id "<RUN_ID>" \
  < "$WORK/fresh.json"
```
Then ask which candidate(s) to pursue. Each pick already has a verified Play URL —
invoke the `clone-app` skill on it. If the user picks nothing, stop — the report
stands on its own.

## Error Handling Summary
| Scenario | Action |
|---|---|
| `fetch-charts.py` / `fetch-play-charts.py` fails | note it, continue with other feeds/web search |
| AppBrain blocks or markup changed | continue on Apple RSS + web signal |
| `play.py resolve` finds no package | flag candidate "Play link unresolved", skip handoff |
| Play link fails WebFetch verify | drop that link; if none verify, flag unresolved |
| `trends.py` returns `{"ok": false}` | WebSearch the same momentum signal |
| numeric source paywalled/JS-only | use only free-visible figures; never invent a number |
| Web search returns thin results | broaden queries within the chosen angle, try another region |
| < 10 candidates survive dedup | loop back to Phase 1/2 with a new angle, re-filter |
| history.json missing/first run | treat as empty; all candidates are fresh |
| User picks nothing | stop after writing the report |
```

- [ ] **Step 2: Verify the skill still references every script/reference that exists**

Run: `grep -o 'scripts/[a-z-]*\.py\|references/[a-z-]*\.md' plugins/market-research/skills/market-research/SKILL.md | sort -u`
Expected: includes `fetch-charts.py`, `fetch-play-charts.py`, `play.py`, `trends.py`, `history.py`, `numeric-sources.md`, `report-template.md`, `scoring-guide.md`, `research-angles.md`.

- [ ] **Step 3: Commit**

```bash
git add plugins/market-research/skills/market-research/SKILL.md
git commit -m "feat(market-research): 8-phase flow — dual-store charts, numeric enrich, Play links"
```

---

## Task 9: Update smoke test, README, and run the full suite

**Files:**
- Modify: `plugins/market-research/tests/smoke-structure.sh`
- Modify: `plugins/market-research/README.md`

**Interfaces:**
- Consumes: all created files.
- Produces: a green `run-all.sh`.

- [ ] **Step 1: Extend `smoke-structure.sh` for the new scripts/refs**

In `plugins/market-research/tests/smoke-structure.sh`, change the scripts loop line:

```bash
for s in fetch-charts.py history.py; do
```
to:
```bash
for s in fetch-charts.py history.py fetch-play-charts.py play.py trends.py; do
```

and change the references loop line:

```bash
for r in research-angles scoring-guide report-template; do
```
to:
```bash
for r in research-angles scoring-guide report-template numeric-sources; do
```

- [ ] **Step 2: Run the smoke test, verify it passes**

Run: `bash plugins/market-research/tests/smoke-structure.sh`
Expected: all `PASS`, exit 0 (new scripts exist + are executable, `numeric-sources.md` present).

- [ ] **Step 3: Update the README**

In `plugins/market-research/README.md`, update the scripts/flow description to list `fetch-play-charts.py`, `play.py` (resolve + count), `trends.py`, and `numeric-sources.md`, and the new 8-phase (0–7) flow with survivor-only enrichment and verified Play links. (Match the existing README's section structure; describe each script in one line as the file already does for `fetch-charts.py`/`history.py`.)

- [ ] **Step 4: Run the FULL suite**

Run: `bash plugins/market-research/tests/run-all.sh`
Expected: structure + all bash + all python tests pass; final line `ALL TESTS PASSED`, exit 0.

- [ ] **Step 5: Confirm the upstream RE tree is untouched**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: prints nothing.

- [ ] **Step 6: Commit**

```bash
git add plugins/market-research/tests/smoke-structure.sh \
        plugins/market-research/README.md
git commit -m "test(market-research): cover v2 scripts in smoke; update README"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** AppBrain charts → Task 1; Play resolver + links → Task 2; saturation → Task 3; Trends best-effort → Task 4; numeric sources → Task 5; numeric scoring → Task 6; report links/citations/saturation → Task 7; survivor-only phase flow + WebFetch verify → Task 8; smoke/README/full-suite + RE-untouched gate → Task 9.
- **Live-markup risk** is handled by the per-scraper "validate against live once" step (Tasks 1 Step 7, 2 Step 8); fix script + fixture together if reality differs, keep the offline test green.
- **No new pip deps, no API keys, all stdlib** — every script mirrors `fetch-charts.py`'s `_http_get` fallback pattern.
- **`trends.py` never hard-fails** — verified by the fallback assertions in Task 4 test.
```
