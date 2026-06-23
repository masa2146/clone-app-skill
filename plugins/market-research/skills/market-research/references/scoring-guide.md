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
| Market opportunity | an installs figure (Play via `play.py resolve`) AND either a Trends `trend_pct` OR a saturation `app_count`. |
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
