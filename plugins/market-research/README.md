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
