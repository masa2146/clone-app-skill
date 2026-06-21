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
