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
