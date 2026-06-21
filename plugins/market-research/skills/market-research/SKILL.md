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
