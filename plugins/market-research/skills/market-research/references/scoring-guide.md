# Scoring Guide

Score every candidate 0–100 as a weighted composite. Three PRIMARY components
(cloneability, market opportunity, monetization fit) plus a secondary tiebreaker
(niche gap). Show the component scores, not just the total, so picks are auditable.

## Components & weights

| Component | Weight | What it measures |
|---|---|---|
| Cloneability | 35% | How cheaply this rebuilds with clone-app + AI. |
| Market opportunity | 35% | Demand, growth, and incumbent weakness. |
| Monetization fit | 20% | Ads/IAP friendliness and category ARPU. |
| Niche gap (tiebreaker) | 10% | Underserved region/language/segment. |

Total = 0.35·clone + 0.35·market + 0.20·monetization + 0.10·niche, each subscore 0–100.

## Scoring each component (0–100)

**Cloneability** — higher = easier:
- 80–100: simple CRUD/utility, few backend endpoints, no heavy ML, standard UI.
- 50–79: moderate backend, some real-time or media, mainstream third-party SDKs.
- 0–49: heavy ML/on-device models, complex real-time/multiplayer, deep native, large content moat.

**Market opportunity** — higher = better:
- 80–100: strong/growing demand, dated or weak incumbents, clear unmet need.
- 50–79: healthy demand, beatable incumbents.
- 0–49: saturated, dominated by entrenched well-funded players.

**Monetization fit** — higher = better:
- 80–100: category with proven ads+IAP and high ARPU (casual games, utilities).
- 50–79: monetizable but moderate ARPU.
- 0–49: hard to monetize / users expect free.

**Niche gap** — higher = more underserved:
- 80–100: clear language/region/segment with no quality option.
- 0–49: well served everywhere.

## Output per candidate

For each candidate keep: `name`, `package` (if resolved), `category`, the four
subscores, the weighted `total`, and a one-line rationale. Rank by `total`
descending. Produce at least 10 candidates AFTER history exclusion.
