# market-research

A Claude Code plugin that autonomously researches the app/game market and surfaces
scored, non-repeating clone candidates, then hands user-chosen candidates to the
`clone-app` plugin for feasibility analysis.

## What it does

`/market-research` runs an 8-phase workflow (0–7):

0. **Seed rotation** — pick varied search angles (category × region × niche) so runs differ.
1. **Gather** — App Store RSS (`fetch-charts.py`) + play.google.com charts (`fetch-play-charts.py`) + Google Trends best-effort (`trends.py`) + free web search.
2. **Synthesize** — cluster findings into ≥10 distinct app/game ideas.
3. **Score** — composite numeric score: cloneability 35 + market 35 + monetization 20 + niche 10 (see `scoring-guide.md` + `numeric-sources.md`).
4. **Dedup** — exclude anything already in `./work/market-research/history.json`.
5. **Present** — show the scored, ranked table.
6. **Survivor-only enrichment** — for user-chosen candidates only: resolve the Play Store package ID (`play.py`) and verify the link is live via WebFetch before handing off.
7. **Handoff** — chosen candidates (with verified Play links) flow into `clone-app`.

## State

Written under `./work/market-research/` in your current directory:
- `history.json` — every past suggestion; the non-repeat memory.
- `research-<date>.md` — the full report for a run.

## Scripts

- `scripts/fetch-charts.py` — fetch Apple App Store RSS chart feeds → normalized JSON.
- `scripts/fetch-play-charts.py` — fetch play.google.com top/category charts → normalized JSON (no AppBrain; uses the public Play web endpoint directly).
- `scripts/play.py` — resolve an app name or bundle ID to a Play Store package ID and count search results (used in survivor-only enrichment, Phase 6).
- `scripts/trends.py` — best-effort Google Trends interest data for a keyword; never hard-fails (falls back to `null` if the endpoint is unavailable).
- `scripts/history.py` — read / append / dedup the suggestion history.

Python is stdlib-only. Tests run offline against `tests/fixtures/`:

```bash
bash plugins/market-research/tests/run-all.sh
```

## References

AI-judgment rubrics under `skills/market-research/references/`:

- `research-angles.md` — rotating category × region × niche seeds for run-to-run variety.
- `scoring-guide.md` — the 0–100 weighted composite formula and per-dimension guidance.
- `numeric-sources.md` — how to map raw data (chart rank, install count, rating, search results) to numeric sub-scores used by `scoring-guide.md`.
- `report-template.md` — output format for the scored candidate table and per-candidate write-ups.

## Effort convention

Effort is measured in **AI Sprints** (one focused Claude session), never calendar time.
