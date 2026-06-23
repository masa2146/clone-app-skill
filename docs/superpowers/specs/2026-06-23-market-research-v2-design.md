# Market Research v2 — Design

**Date:** 2026-06-23
**Plugin:** `plugins/market-research/`
**Status:** Approved, pending implementation plan

## Goal

Make the `market-research` skill produce higher-quality, numerically-grounded,
source-cited clone candidates — entirely free, no API keys. Every candidate must
carry 1–2 real Google Play Store links. Scoring must cite real numbers (installs,
trend %, competitor count) instead of pure AI judgment.

## Constraints (unchanged from repo)

- **Free, no API key, no pip.** Python stdlib only (`urllib`, `json`, `re`,
  `subprocess` for `curl` SSL fallback). bash 4+ at runtime.
- **`plugins/android-reverse-engineering/` is untouched.** This work is confined
  to `plugins/market-research/`.
- **Scrape logic needs a fixture, not a live call.** Each new scraper is tested
  offline against `tests/fixtures/` via a `--html-file` / `--json-file` flag.
- Working dir stays `./work/market-research/` in the user's cwd.
- Scripts-for-deterministic / rubrics-for-judgment split is preserved.

## Honesty on free sources

Not every requested source is cleanly scrapeable. The design routes each to the
method that actually works free:

| Source | Method | Why |
|---|---|---|
| Apple App Store RSS | existing `fetch-charts.py` | Public no-auth JSON feed. Keep. |
| Google Play charts | **`play.google.com` HTML** via new `fetch-play-charts.py` | Play has no public JSON feed, but its server-rendered HTML for `/store/apps/top` and `/store/apps/category/<CAT>` returns ~45–70 ranked app cards carrying real Android packages + names (validated live: 46/46). AppBrain — the original plan's source — is Cloudflare-blocked (HTTP 403) for free scraping, so it was dropped. |
| Play link + stats per candidate | new `play.py resolve` | `play.google.com/store/search?q=…&c=apps` is server-rendered enough to grep the first `details?id=` link; the details page carries rating/installs/last-updated in embedded `ld+json` (same parse clone-app's `scrape-play-store.py` already uses). |
| Saturation / competition density | new `play.py count` | Count distinct `details?id=` links + their ratings on the first Play search results page. Approximate but real. |
| Google Trends | best-effort `trends.py` + WebSearch fallback | No key, but the unofficial endpoint needs a token dance and is fragile under stdlib-only. Script is best-effort and **never hard-fails**; on any failure the skill falls back to WebSearch for the same signal. |
| Statista / Sensor Tower / data.ai / SimilarWeb | curated WebSearch/WebFetch targets in `numeric-sources.md` | Paywalled/JS sites. The free signal is their public blog posts and report summaries, surfaced by WebSearch — not a scraper. |

## Architecture

Same shape as today: `SKILL.md` orchestrates prose phases; deterministic steps are
helper scripts; judgment steps follow reference rubrics.

### New scripts (`skills/market-research/scripts/`)

**`fetch-play-charts.py`**
- Input: a chart kind (`top` = `play.google.com/store/apps/top`, or `category`
  with `--category <CAT>` = `/store/apps/category/<CAT>`), `--region` (Play `gl`
  code), `--limit`, `--html-file` (offline test).
- Output: normalized JSON `{ "source": "google-play", "chart": ..., "region": R,
  "count": N, "entries": [ {rank, name, package, rating} ] }`. (`rating` is
  best-effort and may be `None`; rank+name+package is the load-bearing signal.)
- Mirrors `fetch-charts.py`'s shape and its `curl` SSL fallback.
- Entries carry **real Android `package`s** (unlike Apple's iOS bundle ids),
  parsed from Play app cards: `href="/store/apps/details?id=PKG"` +
  `class="Epkrse …">NAME</div>` (validated live: 46/46 on a category page).

**`play.py`** — two subcommands, both with `--html-file` for offline tests:
- `resolve "<app name>"` → scrape Play search, take the top apps hit, fetch its
  details page, print `{name, package, play_url, rating, installs, last_updated,
  developer}`. Reuses the `ld+json` extraction approach from clone-app's
  `scrape-play-store.py` (re-implemented locally — market-research stays
  self-contained per the repo's per-plugin-layout convention; no cross-plugin
  script dependency).
- `count "<query>"` → scrape Play search results, print `{query, app_count,
  avg_rating, top_packages: [...]}` for saturation. `app_count` is "apps on the
  first results page", stated as approximate in the report.

**`trends.py`** (best-effort, never hard-fails)
- `"<term>"` → attempt Google Trends interest-over-time + rising queries via the
  unofficial endpoint (token dance in stdlib). On ANY failure, exit 0 with
  `{"ok": false, "fallback": "websearch"}` so the skill knows to fall back to
  WebSearch for the same momentum signal. `--json-file` for offline test of the
  parser.

### New reference (`skills/market-research/references/`)

**`numeric-sources.md`** — for each free numeric source: what it's good for, the
exact WebSearch query shape to use, which number to extract, and how to cite it.
Covers Google Trends, play.google.com (installs/rating), Statista, Sensor Tower
blog, data.ai, SimilarWeb free tier. This is the rubric that turns "go search the web" into "pull these
specific numbers from these specific places."

### Rewritten references

**`scoring-guide.md` → numeric scoring.** Each subscore must cite at least one
number or it is capped low (e.g. a market score >70 requires an installs figure
AND either a trend % or a competitor count). Adds a per-subscore "evidence" field
to each candidate object. Keeps the existing weights
(cloneability 35 / market 35 / monetization 20 / niche 10).

**`report-template.md`.** Adds: a **Play links** column (1–2 verified links per
candidate); **source citations** inline on every "why now" claim and every number;
a **saturation** figure per candidate; numeric evidence in the per-candidate
detail block.

### Rewritten orchestrator (`SKILL.md`)

New phase flow, with an explicit **efficiency rule**: enrich only the survivors,
not all raw candidates.

```
Phase 0  Seed rotation         (unchanged)
Phase 1  Gather charts         Apple RSS (fetch-charts.py) + play.google.com
                               charts (fetch-play-charts.py) per region
Phase 2  Trend + numeric       WebSearch per numeric-sources.md; trends.py per
                               top themes (fallback to WebSearch on failure)
Phase 3  Synthesize >=12       cluster charts + signal into ideas; Android
                               packages now available from the Play charts
Phase 4  Cheap score + dedup   score on chart/trend signal only; history.py
                               filter; loop for more if <10 survive
Phase 5  Enrich survivors      for the surviving top ~10 ONLY: play.py resolve
                               (1-2 links) + WebFetch verify each link (200 +
                               package match) + play.py count (saturation) +
                               trends.py momentum
Phase 6  Re-score numeric      apply scoring-guide with real numbers + evidence
Phase 7  Present + handoff     fill report-template (Play links, citations,
                               saturation); history.py add; resolve picks to
                               Play URL; invoke clone-app skill
```

Efficiency: the expensive per-candidate work (Play resolve, WebFetch verify,
saturation, trends) happens in Phase 5 against ~10 survivors, never against the
full raw synthesis set.

## Link verification

In Phase 5, each resolved Play URL is WebFetched and confirmed (HTTP 200 and the
`id=` package present on the page) before it is written into the report. Dead or
mismatched links are dropped; a candidate with no verifiable Play link is kept in
the report flagged "Play link unresolved" and skipped on clone-app handoff (same
rule as today's iOS-only case).

## Out of scope

- Cross-platform gap detection (iOS-popular / Android-missing) — explicitly cut.
- AppBrain as a chart source — Cloudflare-blocked (403), dropped for play.google.com.
- Top-grossing Play chart — Play exposes no clean grossing URL without JS; Apple
  RSS `topgrossingapplications` carries the monetization-rank signal instead.
- Any pip dependency, API key, or paid tier.
- Changes outside `plugins/market-research/`.

## Testing

- `fetch-play-charts.py`, `play.py` (both subcommands), `trends.py` each get an
  offline fixture test driven by `--html-file` / `--json-file`. New fixtures:
  a Play chart-page HTML, a Play search results HTML, a Play details HTML, a
  Trends JSON response.
- Each scraper's first implementation task: fetch live once, save the fixture,
  confirm the parser. Then all subsequent tests run offline.
- `run-all.sh` and `smoke-structure.sh` extended to cover the new scripts/refs.
- Existing bash test convention kept: `set -uo pipefail`, aggregate failures.

## Risks

- **Play HTML class-name drift** (Play obfuscates classes like `Epkrse`, which can
  rotate). Mitigation: fixture-driven parser isolates the brittle selector; the
  package link (`/store/apps/details?id=`) is stable even when title classes
  rotate, so rank+package survives a class change; the skill notes a failed
  Play-chart fetch and continues on Apple RSS + web signal.
- **Google Trends fragility.** Mitigation by design: `trends.py` never hard-fails;
  WebSearch fallback covers the same signal.
- **Play search HTML variance by region/locale.** Mitigation: force an `hl=en&gl=US`
  query in `play.py` for stable markup; fixture covers that shape.
