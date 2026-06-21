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
