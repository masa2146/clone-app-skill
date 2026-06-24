# Market Research Report Template

Fill every section. Write to `./work/market-research/research-<YYYY-MM-DD>.md`.
Every number carries a source link. Every candidate carries 1–2 Google Play links.

---

# Market Research — <YYYY-MM-DD>

## Run parameters
- Angles this run: <categories / regions / niche lens chosen in Phase 0>
- Focus argument: <the user's focus, or "none">
- Sources: Apple RSS (<feeds/regions>) + play.google.com charts (<charts>) + web numeric (<sources>) + Trends (<ok/fallback>)
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
