# Market-to-Build Pipeline — Design Spec

**Date:** 2026-06-22
**Status:** Approved (brainstorming complete)
**Scope:** Two new plugins (`market-research`, `hermes-build`) plus a one-branch edit to the
existing `clone-app` plugin, chaining into a full *discover → analyze → build* pipeline.

## 1. Purpose

Give the user an end-to-end loop:

1. **Discover** — autonomously research the app/game market and surface ≥10 fresh,
   scored clone candidates that do not repeat across runs.
2. **Pick** — the user selects one or more candidates.
3. **Analyze** — each pick flows into the existing `clone-app` feasibility skill.
4. **Build** — on approval, hand off to a new `hermes-build` skill that generates the
   capability bundle [hermes-agent](https://github.com/nousresearch/hermes-agent) lacks
   (Firebase, Play publish, ads) and best-effort drives hermes to build → test →
   Firebase → ads → upload to the Play **internal testing** track.

Effort throughout stays measured in **AI Sprints** (one focused session), never calendar time —
consistent with the existing clone-app convention.

## 2. The hard constraint (unchanged)

`plugins/android-reverse-engineering/` stays byte-identical to upstream. Before any commit:

```bash
git status --porcelain plugins/android-reverse-engineering/   # must print nothing
```

All new work lives under `plugins/market-research/` and `plugins/hermes-build/`. The only
edit to shared/existing files: `clone-app`'s Phase 7 (one new branch) and root
`.claude-plugin/marketplace.json` (two new plugin entries).

## 3. hermes-agent — what it is, what it lacks

Established by research (github.com/nousresearch/hermes-agent, MIT, v0.17.0):

- **Is:** a self-hosted agent framework + runtime. Executes shell/Python/build tools/tests/git
  across six backends (local, Docker, SSH, Singularity, Modal, Daytona). Any LLM provider
  (no vendor lock-in). Interfaces: CLI (`hermes`), Python SDK (`from run_agent import AIAgent`),
  HTTP gateway.
- **Lacks (no built-in tool):** Firebase integration, Google Play publisher automation, AdMob/ads
  configuration, Android emulator orchestration. These are added via **custom hermes skills**
  (`~/.hermes/skills/`), **MCP servers**, or **shell delegation** (`firebase`, `gcloud`,
  `bundletool`, `fastlane`).

**Consequence:** "fully autonomous dev→publish" is not a built-in button. `hermes-build` generates
the missing capabilities as a bundle, then lets hermes execute them. This is the integration model
the user chose (generate skill + MCP config bundle).

## 4. Architecture

```
plugins/
  android-reverse-engineering/   [upstream, untouched]
  clone-app/                     [existing — only Phase 7 gains one branch]
  market-research/               [NEW]
  hermes-build/                  [NEW]
```

**Pipeline (chained handoffs, no central orchestrator):**

```
/market-research
   → free web gather + LLM trend synthesis, history-excluded
   → ≥10 scored ideas → user picks N
   → for each pick: offer "run clone-app feasibility?" → invoke clone-app skill
clone-app  (existing 8 phases, unchanged)
   → Phase 7 decision gate, NEW third branch "Build with hermes"
   → invoke hermes-build (passing report + stack + payloads.json)
hermes-build
   → preflight (best-effort) → mission brief → capability bundle → drive hermes
   → signed AAB → Play internal testing track → build-report
```

Handoff style matches the existing `clone-app → writing-plans` chain. Each plugin is independently
installable and testable.

## 5. Decisions locked in brainstorming

| # | Decision | Choice |
|---|----------|--------|
| Scope | How much to build | Full pipeline, end to end |
| Data source | Market research inputs | Free web (WebSearch + Play charts + App Store RSS) **+** LLM trend synthesis. $0, no paid intel API. |
| Freshness | Avoid repeat ideas | History file; each run excludes/deprioritizes prior suggestions |
| Ranking | What makes a good candidate | Composite score: **Cloneability + Market opportunity + Monetization fit** (primary); niche gap (secondary tiebreaker) |
| Hermes integration | How we drive hermes | Generate hermes **skill + MCP config bundle** that fills hermes's gaps |
| Publish boundary | How far autonomy goes | Build signed AAB → **Play internal testing track only**. Stops before production. Reversible. |
| Packaging | Repo layout | **Three plugins** (market-research, clone-app, hermes-build) |
| Orchestration | Who drives the chain | **Chained handoffs** — each skill offers the next |
| Missing prereqs | hermes/creds not set up | **Best-effort + skip** with warnings. Never half-fails. |

## 6. Plugin: `market-research`

**Goal:** autonomous market scan → ≥10 scored, non-repeating clone candidates.

**Skill:** `skills/market-research/SKILL.md` — phased prose orchestrator (clone-app pattern).

**Phases:**

- **P0 — Seed rotation.** Pick varied search angles this run (category × region × niche), read
  from `references/research-angles.md` (rotating list, e.g. hyper-casual games, utilities,
  fintech LATAM, AI tools, health). Variety comes from rotated seeds + history exclusion.
- **P1 — Gather (free web).** WebSearch + scrape: Play top-charts pages, App Store RSS feeds
  (`itunes.apple.com/<region>/rss/topfreeapplications`), ProductHunt/Reddit/trend articles.
  Helper `fetch-charts.py` (stdlib, offline-fixture-tested) returns structured chart data; the
  model synthesizes emerging trends from the search results.
- **P2 — Synthesize candidates.** LLM clusters findings into ≥10 distinct ideas; each carries:
  name, category, what-it-does, why-now (trend signal), incumbent(s), monetization model.
- **P3 — Score.** Composite per `references/scoring-guide.md`: cloneability (tech-stack-simplicity
  guess, backend surface, no heavy ML), market opportunity (demand/growth/weak incumbents),
  monetization fit (ads/IAP, ARPU category) — all primary; niche gap secondary. Weighted 0–100,
  ranked.
- **P4 — History dedup.** Exclude/deprioritize anything in
  `./work/market-research/history.json`. Append new picks after presentation.
- **P5 — Present + handoff.** Show ranked table (≥10). User picks N. For each pick, resolve to a
  real Play package/URL (Play search if the synthesized idea named an app without a package — the
  downstream `extract-package.sh` needs a concrete package), then offer "run clone-app feasibility
  on this?" → invoke `clone-app`.

**State** (user cwd, never inside the plugin) — `./work/market-research/`:
- `history.json` — every past suggestion (package/name + date + run-id): the non-repeat memory.
- `research-<YYYY-MM-DD>.md` — this run's full report.

**Scripts** (`scripts/`, each testable, stdlib-only):
- `fetch-charts.py` — chart/RSS fetch → JSON; `--html-file` / `--json-file` for offline fixtures.
- `history.py` — read / append / dedup `history.json`.

**References** (`references/`): `research-angles.md`, `scoring-guide.md`, `report-template.md`.

**Tests** (`tests/`): chart/RSS fixtures, history-dedup test, scoring sanity, `smoke-structure.sh`.
Offline-fixture pattern, no network — same discipline as clone-app.

## 7. Plugin: `clone-app` (edit only)

Single change: **Phase 7 decision gate** gains a third branch.

Existing branches: **Yes** → `superpowers:writing-plans`; **No** → stop.
New branch: **"Build with hermes"** → invoke `hermes-build`, passing the clone report, the
user-selected stack (Phase 4), and `$WORK/payloads.json` (backend API surface).

No other clone-app file changes. The upstream RE plugin is not touched.

## 8. Plugin: `hermes-build`

**Goal:** take a clone-report + plan, generate the capability bundle hermes lacks, then best-effort
drive hermes to build → test → Firebase → ads → Play internal-testing track.

**Skill:** `skills/hermes-build/SKILL.md` — phased.

**Phases:**

- **P0 — Preflight (best-effort, never blocks).** Probe for: `hermes` binary, `firebase-tools`,
  `fastlane`/`bundletool`, Play service-account JSON, signing keystore, AdMob app/unit IDs. Write
  `preflight.json` (available/missing). Each missing capability marks its later steps `SKIP` with a
  warning; the pipeline continues.
- **P1 — Generate mission brief.** `mission-brief.md` = structured spec hermes consumes: app name,
  target stack, feature list, backend API surface (from `payloads.json`), Firebase services needed,
  ads placement, build target = **signed AAB → Play internal testing only** (stops before
  production).
- **P2 — Generate hermes capability bundle.** Emit into `./work/<pkg>/hermes/`:
  - hermes **skills** (hermes skill format): `firebase-setup`, `play-publish`
    (fastlane supply → internal track), `admob-wire`, `android-build` (gradle / AAB sign).
  - **MCP config** stub (Firebase CLI / Play API where MCP fits).
  - `hermes.config` snippet (backend = Modal/Docker, model provider).
  - Steps whose prereq was missing in P0 are marked `SKIP` in the brief.
- **P3 — Drive hermes (best-effort).** If `hermes` present: feed the mission brief to hermes
  (`hermes` CLI / SDK `AIAgent.run_conversation`), stream progress — hermes autonomously scaffolds →
  builds → tests → Firebase init → ads wire → signs AAB → uploads internal track. If `hermes`
  absent: skip the drive, hand the user the bundle + brief + run instructions.
- **P4 — Report.** `build-report-<YYYY-MM-DD>.md`: what ran, what skipped (and why — missing creds),
  AAB path, internal-track upload status, and explicit next manual steps. Promotion to production is
  manual and out of scope.

**State** — `./work/<pkg>/hermes/`: bundle files, `mission-brief.md`, `preflight.json`,
`build-report-<date>.md`.

**Scripts** (`scripts/`, testable): `preflight.sh` (capability probe → JSON), `gen-bundle.py`
(templates → hermes skill files; template-driven, fixture-tested), `drive-hermes.sh` (invoke hermes
if present, else print instructions).

**References:** `bundle-templates/` (firebase / play / admob / android-build skill templates),
`mission-brief-template.md`.

**Tests:** preflight-probe (mock present/missing), gen-bundle output vs fixtures,
`smoke-structure.sh`. No live hermes / Play / Firebase calls in tests.

**Boundaries (explicit):**
- Never auto-promotes past the internal testing track to production.
- Never spends money or publishes without pre-existing user credentials.
- Missing creds → skip + warn, never a hard fail.
- Legal/publishing liability surfaced in the build-report; the existing clone-app legal note still
  governs which apps may be analyzed/cloned at all.

## 9. Cross-cutting conventions (inherited from clone-app)

- **Working dir** is `./work/...` relative to the user's cwd — never inside any plugin.
- **Scripts** use `#!/usr/bin/env bash`, run via `bash <path>`; Python is **stdlib-only**
  (`urllib`, `json`, `re`); no pip, no virtualenv.
- **Tests** use `set -uo pipefail`, aggregate failures, exit non-zero if any fail. Python scrapers
  tested offline against `tests/fixtures/` via `--html-file` / `--json-file`. New scrape logic needs
  a fixture, not a live call.
- **Commits** follow Conventional Commits scoped per plugin:
  `feat(market-research): …`, `feat(hermes-build): …`.
- **Marketplace:** add both plugins to root `.claude-plugin/marketplace.json`; each plugin carries
  its own `.claude-plugin/plugin.json`.

## 10. Build order (each gets its own implementation plan)

This umbrella spec decomposes into three implementation plans, built and tested in order:

1. **`market-research`** — standalone value first; hands to existing clone-app manually until the
   chain edit lands.
2. **`clone-app` Phase 7 edit** — one branch; small.
3. **`hermes-build`** — largest; depends on the brief/bundle contract.

Each plan is produced via the `writing-plans` skill and verified by its own test suite before the
next begins.

## 11. Out of scope

- Paid market-intelligence APIs (SensorTower / data.ai / AppMagic).
- Autonomous production publishing, live AdMob spend, or any irreversible Play Console action.
- Installing/bootstrapping hermes or its credentials on the user's machine (best-effort detect only).
- Modifying the upstream `android-reverse-engineering` plugin.
- iOS build/publish (Play/Android only).
