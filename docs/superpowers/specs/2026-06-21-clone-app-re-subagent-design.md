# Clone App — RE-via-Subagent + Payload Extraction Design Spec

**Date:** 2026-06-21
**Scope:** `plugins/clone-app/` only. `plugins/android-reverse-engineering/` stays byte-identical (upstream-untouched rule).
**Supersedes:** Phase 2 of the original `2026-06-21-clone-app-skill-design.md`. All other phases unchanged unless noted.

## Problem

Two gaps in the current clone-app skill:

1. **The RE skill never runs.** clone-app Phase 2 calls the `android-reverse-engineering` plugin's bash *scripts* directly (via `resolve-re-scripts.sh`). The RE *skill's* prose workflow — fingerprint triage, two-tier API documentation, BuildConfig secret hunting, call-flow tracing, cross-platform `.ps1` handling — is bypassed. clone-app re-implements a thin, lossy version of it inline. The user never observes the RE skill triggering because it genuinely does not.

2. **Payloads are not extracted.** Phase 2 assembles only an endpoint *list* (host/method/path/auth). Request bodies, response shapes, and headers — the RE skill's "Tier 2" detail — are never produced and never persisted. Nothing reaches memory or the feasibility report.

## Decisions (locked during brainstorming)

- **Q1 → C (hybrid w/ fallback):** Invoke the `android-reverse-engineering` **skill** for the heavy RE workflow when it is installed; **fall back to direct scripts** when it is not. Full workflow when available, graceful degradation otherwise.
- **Q2 → A (subagent isolation):** RE runs inside a dispatched subagent, in its own context. The orchestrator never ingests raw decompiled sources — only a concise summary plus on-demand file reads.
- **Q3 → B (targeted payloads):** Tier-2 payloads (request body, response shape, headers, params) for **auth, payment/checkout, and the 1–2 core feature endpoints**. Tier-1 flat inventory for everything else. Matches the RE skill's own "Tier-1 always, Tier-2 for ~10 high-value" guidance.
- **Memory → 1 (durable files):** Full detail written to files in `$WORK/`, off-context, re-readable. Only a ≤40-line summary enters orchestrator context.

## Architecture — Phase 2 rewrite (probe → dispatch → consume)

```
Phase 2a  PROBE     resolve-re-scripts.sh → are RE scripts on disk? (exit code)
                    orchestrator's skill list → is the RE skill registered?
Phase 2b  DISPATCH  dispatch a subagent (Agent tool, general-purpose) that runs RE
                    in isolation:
                       ├─ RE skill registered → subagent invokes the
                       │                         android-reverse-engineering skill
                       └─ skill absent, scripts present → subagent runs direct scripts
                    Subagent writes digest files to $WORK/, returns the summary text.
Phase 2c  CONSUME   orchestrator reads $WORK/re-summary.txt only; pulls
                    re-digest.md / payloads.json on demand in later phases.
```

**Invariant:** both branches write the **same digest files**, so Phases 3–7 are branch-agnostic — one consume path regardless of how RE ran.

### Branch decision table

| RE skill registered | RE scripts on disk | Action |
|---|---|---|
| ✓ | — | subagent runs **RE skill** (preferred) |
| ✗ | ✓ | subagent runs **direct scripts** (fallback) |
| ✓ | ✓ | subagent runs **RE skill** (skill wins) |
| ✗ | ✗ | **stop** — show `resolve-re-scripts.sh` error |

Two independent facts drive it: skill availability (orchestrator reads its own available-skills list) and script availability (`resolve-re-scripts.sh` exit code). `resolve-re-scripts.sh` is unchanged — it remains both the probe and the fallback locator.

**Why the subagent wraps the script-fallback branch too** (not only the skill branch): keeps decompile noise out of the orchestrator either way, and keeps Phases 3–7 on a single branch-agnostic consume path.

## Digest contract (subagent output)

Single source of truth: a new reference file `references/re-digest-contract.md`. The Phase-2 subagent prompt points at it. The subagent MUST write three files to `$WORK/` and return the summary.

### `$WORK/re-digest.md` — human-readable main artifact

```
# RE Digest — <pkg>
## Framework & Stack    framework, HTTP lib, DI, serialization, obfuscation level
## Hosts                first-party vs third-party (table)
## Endpoint Inventory   Tier-1: host | method | path | auth | source file
## Key Flow Payloads    Tier-2: auth, payment/checkout, 1-2 core
                        — request body / response shape / headers / params
## BuildConfig Secrets  base URLs, API keys, feature flags, flavors
## Feature Signals      screen count, SDKs, permissions, components
## RE Method            "re-skill" | "direct-scripts" | "limited: <framework>"
```

### `$WORK/payloads.json` — machine-readable (memory requirement)

```json
{
  "package": "com.example.app",
  "re_method": "re-skill",
  "endpoints": [
    {
      "host": "api.example.com",
      "method": "POST",
      "path": "/v1/auth/login",
      "auth": "none",
      "source": "com/example/api/AuthApi.java",
      "request_body": { "email": "string", "password": "string" },
      "response": { "token": "string", "user": {} },
      "headers": { "Content-Type": "application/json" }
    }
  ],
  "buildconfig": { "BASE_URL": "https://api.example.com/v1" }
}
```

`request_body` / `response` are `null` for Tier-1-only endpoints. Populated only for auth/payment/core (Tier-2).

### `$WORK/re-summary.txt` — ≤40 lines, the only RE text entering orchestrator context

Contains: framework, host count, endpoint count, key-flow names, secrets-found count, RE method, blockers/warnings. The subagent's return value = contents of `re-summary.txt` + the two file paths. **The subagent must not dump raw decompiled sources into its return.**

### Contract rules

- **Tier-2 only for auth / payment / core** (decision Q3=B). All other endpoints → Tier-1 row, `null` payloads.
- **Framework guard:** if fingerprint reports Flutter / React Native / Cordova / Xamarin, the subagent writes a partial digest, sets `RE Method: limited: <framework>`, and payloads may be empty. Downstream widens the uncertainty band.

## Subagent dispatch

clone-app dispatches via the **Agent tool** (`general-purpose` type — can both invoke skills and run bash). The single prompt carries: `$PKG`, `$APK`, `$WORK`, the chosen branch, and the digest contract verbatim (or a pointer to `re-digest-contract.md`). Subagent steps:

1. Run RE — the skill or the direct scripts, per branch.
2. Extract Tier-1 inventory + Tier-2 payloads for auth/payment/core.
3. Write `re-digest.md`, `payloads.json`, `re-summary.txt`.
4. Return `re-summary.txt` contents + the two file paths. No raw sources.

## Downstream changes (Phases 3–7)

- **Phase 2c:** orchestrator reads `re-summary.txt` only; reads `re-digest.md` / `payloads.json` on demand if a later phase needs detail.
- **Phase 5 (effort/cost):** read `payloads.json`; endpoint count + payload complexity feed the AI-Sprint estimate (backend surface = real work) instead of a loose guess.
- **Phase 6 (report):** new optional report section **"Backend API Surface"** — Tier-1 table summary + key-flow payloads from the digest.
- **Error table additions:**
  - RE subagent fails → retry once, then fall back to direct-scripts branch (if scripts present); else stop.
  - Both branches unavailable → stop with the resolver error.

## Files changed (all under `plugins/clone-app/`)

| File | Change |
|---|---|
| `skills/clone-app/SKILL.md` | Rewrite Phase 2 (probe/dispatch/consume); tweak Phases 5 & 6; extend error table |
| `skills/clone-app/references/re-digest-contract.md` | **New** — digest schema, single source of truth for the subagent |
| `skills/clone-app/scripts/resolve-re-scripts.sh` | Unchanged (remains probe + fallback locator) |
| `tests/fixtures/re-digest.sample.md` | **New** — schema fixture |
| `tests/fixtures/payloads.sample.json` | **New** — schema fixture |
| `tests/test-re-digest-contract.sh` | **New** — structural assertions |
| `tests/smoke-structure.sh` | Add new reference file to present-files check |

`plugins/android-reverse-engineering/` is **untouched** — the subagent *invokes* it, never edits it. `git status --porcelain plugins/android-reverse-engineering/` must stay empty.

## Tests (offline, fixture-based — matches existing pattern)

- `test-re-digest-contract.sh` asserts:
  - `re-digest-contract.md` lists every required `re-digest.md` section and every required `payloads.json` key.
  - `SKILL.md` Phase 2 references the contract, names both branches, and dispatches a subagent.
  - Sample fixtures parse (JSON valid; digest has all sections).
- `smoke-structure.sh` gains the new reference file in its existence check.
- **No live RE run in tests** — decompilation is too heavy and non-deterministic. Contract + wiring asserted structurally, same philosophy as the offline Python scraper tests.

## Non-goals

- Exhaustive Tier-2 payloads for every endpoint (Q3=C rejected — token-expensive, RE skill itself warns against it).
- Modifying any upstream RE file.
- Live decompilation inside the test suite.
