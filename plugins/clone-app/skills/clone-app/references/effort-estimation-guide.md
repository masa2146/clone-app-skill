# Effort Estimation Guide (Phase 5) — AI-Assisted Units

Estimate in **AI Sprints**, NOT human days. 1 AI Sprint = one focused Claude
Code session producing a reviewable increment (~2-4h human review time).

## Method
1. Build the feature list from RE output:
   - Screens = Activity + Fragment count (dedupe obvious base classes).
   - API surface = endpoint count from find-api-calls.
   - Integrations = third-party SDKs (auth, payment, maps, analytics, push, chat).
   - Backend = REST/GraphQL/WebSocket presence + first-party host count.
2. Assign each feature a complexity and sprint range using the table below.
3. Sum to a range (min–max sprints). Never give a single false-precise number.

## Reference sprint costs
| Feature class | Low | Typical | High | Notes |
|---|---|---|---|---|
| Project scaffold + CI | 0.5 | 1 | 1 | nav, theming, state mgmt setup |
| Auth (email/social) | 1 | 1.5 | 2 | +1 if custom backend auth |
| Simple list/detail screen | 0.3 | 0.5 | 1 | per screen, AI-fast |
| Complex interactive screen | 1 | 2 | 3 | maps, editors, realtime |
| API integration layer | 1 | 2 | 3 | scales with endpoint count |
| Each major SDK integration | 0.5 | 1 | 2 | payment > maps > analytics |
| Custom backend (CRUD) | 2 | 4 | 8 | scales with entity + endpoint count |
| Realtime (WebSocket/push) | 1 | 2 | 4 | |
| Offline/sync | 2 | 3 | 5 | |
| Polish/QA/store submission | 1 | 2 | 3 | |

## Obfuscation caveat
If RE flagged heavy R8/Flutter (feature list incomplete), add a **+20-40%
uncertainty band** and state it explicitly in the report.

## Output
A table: Category | Complexity | Sprints (min–max), then a TOTAL row.
