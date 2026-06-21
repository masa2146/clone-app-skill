# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** (a fork of `SimoneAvogadro/android-reverse-engineering-skill`) hosting two plugins:

- `plugins/android-reverse-engineering/` — **upstream, vendored. Never modify.** Decompiles APK/XAPK/JAR/AAR with jadx, extracts HTTP APIs, recovers R8-obfuscated Kotlin names.
- `plugins/clone-app/` — **this project's work.** A `/clone-app` skill that takes a Google Play URL, drives the RE plugin to reverse engineer the app, scrapes store metrics, estimates AI-assisted clone effort + infra cost, writes a viability report, and optionally hands off to the `writing-plans` skill.

There is no compiled artifact and no application runtime. "The code" is bash + Python helper scripts plus Markdown skill/command/reference docs that Claude Code loads at session time.

## The hard constraint

`plugins/android-reverse-engineering/` is the upstream tree. Keeping it byte-identical is what makes `git pull upstream master` conflict-free. Before committing, this must print nothing:

```bash
git status --porcelain plugins/android-reverse-engineering/
```

Two remotes: `origin` = `masa2146/clone-app-skill` (this fork), `upstream` = `SimoneAvogadro/android-reverse-engineering-skill`. Sync upstream with `git pull upstream master`. The only shared files clone-app touches are root `.claude-plugin/marketplace.json` (added a second plugin entry) and—if ever—root `README.md`; everything else lives under `plugins/clone-app/`.

## Commands

```bash
# Full clone-app test suite (5 suites, ~28 assertions). Run from repo root.
bash plugins/clone-app/tests/run-all.sh

# A single test
bash    plugins/clone-app/tests/test-extract-package.sh
python3 plugins/clone-app/tests/test-scrape-play-store.py

# Structural smoke test: files present, scripts executable, JSON valid, both plugins in marketplace
bash plugins/clone-app/tests/smoke-structure.sh

# Validate the two JSON manifests
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); json.load(open('plugins/clone-app/.claude-plugin/plugin.json'))"
```

Shell is zsh but every script uses `#!/usr/bin/env bash` — invoke with `bash <path>`, not `sh`. `shopt` etc. fail under zsh; wrap in `bash -c '...'`. Python is stdlib-only (`urllib`, `json`, `re`); no pip, no virtualenv.

**bash 4+ is required at runtime.** The upstream RE scripts (`fingerprint.sh`, `find-api-calls.sh`) use `${VAR,,}` and break with "bad substitution" on macOS's stock bash 3.2. You cannot patch them (upstream-untouched rule), so the fix is `brew install bash`; `#!/usr/bin/env bash` then resolves to the modern one. `resolve-re-scripts.sh` emits a stderr WARNING when it detects bash < 4.

**APK source is APKCombo, not APKPure.** The old `d.apkpure.com/b/APK/<pkg>` endpoint now returns an HTTP 403 Cloudflare challenge for every package. `download-apk.sh` instead GETs `apkcombo.com/app/<pkg>/download/apk` with a browser User-Agent, greps the embedded `/r2?u=<signed-url>` link out of the HTML, and downloads that (no JavaScript needed; the URL slug segment is ignored by the server so a literal `app` works for any package).

## How clone-app is wired

`plugins/clone-app/skills/clone-app/SKILL.md` is the orchestrator — an 8-phase (0–7) prose workflow Claude executes. Phases split into two kinds:

- **Deterministic steps → helper scripts** under `skills/clone-app/scripts/`, each independently testable: `extract-package.sh` (Play URL → package), `download-apk.sh` (APKCombo two-step download, 3 retries, apk-vs-xapk by ZIP contents), `resolve-re-scripts.sh` (locates the sibling RE plugin's `scripts/` dir + warns if `bash` is < 4), `scrape-play-store.py` (Play page → metrics JSON via embedded ld+json), `check-appstore.py` (iTunes Search → iOS presence).
- **AI-judgment steps → reference rubrics** under `skills/clone-app/references/` (`stack-recommendation-guide`, `effort-estimation-guide`, `infra-cost-guide`, `report-template`). These keep effort/cost/verdict output consistent; edit the rubric, not the prose, to change how estimates are produced.

clone-app never hardcodes RE script paths. It calls `resolve-re-scripts.sh`, which from `plugins/clone-app/` walks to `plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/` (honoring `$CLAUDE_PLUGIN_ROOT`, falling back to deriving its own location). Phase 2 then invokes that dir's `fingerprint.sh`, `check-deps.sh`, `decompile.sh -o "$WORK/output"`, `recover-kotlin-names.sh`, `find-api-calls.sh`.

Two runtime conventions the scripts and SKILL.md share:
- **Working dir** is `./work/{package}/` relative to the user's cwd (never inside the plugin). Decompile output must land at `$WORK/output/` via `decompile.sh -o` — `decompile.sh` otherwise defaults to a relative `<basename>-decompiled` dir in cwd.
- **Effort is measured in "AI Sprints"** (one focused Claude session, ~2–4h review), never calendar time.

SKILL.md pauses for the user at exactly two points: Phase 4 (choose clone stack) and Phase 7 (proceed to implementation plan?). Phase 7's "yes" path invokes `superpowers:writing-plans`.

## Test pattern

Bash tests use `set -uo pipefail` (intentionally not `-e`) and aggregate failures into a `fail` var so every assertion runs; the script exits non-zero if any failed. Python scrapers are tested offline against `tests/fixtures/` via `--html-file` / `--json-file` flags — never hitting the network. New scrape logic needs a fixture, not a live call.

## Conventions

- Plugin/skill identity is layered: `marketplace.json` top-level `name` (`clone-app-skill`) is what `/plugin install clone-app@clone-app-skill` resolves against; each plugin's `.claude-plugin/plugin.json` carries its own `name`. The upstream plugin entry inside `marketplace.json` stays attributed to Simone Avogadro.
- Commits follow Conventional Commits scoped to the plugin: `feat(clone-app): …`, `test(clone-app): …`, `chore(clone-app): …`.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` hold the design spec and the task-by-task implementation plan this plugin was built from — read them for the rationale behind a phase or script.
