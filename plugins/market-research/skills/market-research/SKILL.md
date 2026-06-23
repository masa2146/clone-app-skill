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

## Phase 1: Gather charts (free)
For each chosen region pull BOTH stores. Apple RSS (iOS signal — bundle ids, not
Android packages):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-charts.py \
  topfreeapplications --region <region> --limit 25 > "$WORK/charts-<region>-free.json"
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-charts.py \
  topgrossingapplications --region <region> --limit 25 > "$WORK/charts-<region>-grossing.json"
```
play.google.com charts (Android signal — REAL packages). Pull the overall top
plus one category page per chosen category (Play category code, e.g.
`PRODUCTIVITY`, `GAME_PUZZLE`, `FINANCE`):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-play-charts.py \
  top --region <region> --limit 25 > "$WORK/play-top-<region>.json"
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-research/scripts/fetch-play-charts.py \
  category --category <CAT> --region <region> --limit 25 > "$WORK/play-<CAT>.json"
```
If any fetch fails (Play may rotate its obfuscated title class), note it and
continue with the feeds you got — Apple RSS + web signal still stand.

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
Cluster chart entries (Apple RSS + play.google.com) + web findings into ≥12
distinct ideas (synthesize > 10 so dedup still leaves ≥10). For each: name,
category, what-it-does, why-now (with a cited number where available),
incumbent(s), monetization model. play.google.com entries already give an
Android `package`; carry it.
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
| play.google.com chart fetch fails / title class rotated | continue on Apple RSS + web signal; package link stays stable |
| `play.py resolve` finds no package | flag candidate "Play link unresolved", skip handoff |
| Play link fails WebFetch verify | drop that link; if none verify, flag unresolved |
| `trends.py` returns `{"ok": false}` | WebSearch the same momentum signal |
| numeric source paywalled/JS-only | use only free-visible figures; never invent a number |
| Web search returns thin results | broaden queries within the chosen angle, try another region |
| < 10 candidates survive dedup | loop back to Phase 1/2 with a new angle, re-filter |
| history.json missing/first run | treat as empty; all candidates are fresh |
| User picks nothing | stop after writing the report |
