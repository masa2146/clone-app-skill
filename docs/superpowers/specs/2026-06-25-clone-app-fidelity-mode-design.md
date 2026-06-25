# clone-app Fidelity Mode — Design

**Date:** 2026-06-25
**Status:** Approved design, pre-implementation
**Plugin:** `plugins/clone-app/`

## 1. Problem & goal

The `clone-app` skill today is **feasibility-oriented**: it downloads an APK,
reverse engineers a shallow slice of it, scrapes store metrics, estimates
AI-Sprint effort and infra cost, and produces a GO / NO-GO viability verdict.

A second use case has emerged that the current shape serves poorly: the user
does not care about pricing or a verdict. They want to **extract and replicate
an app or game in high fidelity** — its workflows (iş akışları), its designs,
its in-app/business logic, and, where it can be inferred, its backend design.

This spec adds a **fidelity mode** to `clone-app`. The mode reorients the skill
from "should I clone this and what will it cost" toward "capture everything
needed to rebuild this faithfully." Feasibility remains the default behavior;
fidelity is opt-in and does not break the existing path.

## 2. Scope

**In scope (Phase A — static deep extraction):**
- A fidelity mode toggle that skips the feasibility phases and deepens the
  extraction phases.
- Full Tier-2 payload extraction across **all first-party endpoints** (not just
  the auth/payment/core trio the feasibility path limits itself to).
- New extraction of **in-app logic / workflows** (ViewModels, use-cases,
  validation rules, state machines, local DB schema, game formulas).
- New extraction of the **real navigation graph** (not inferred).
- A new **inferred backend design** document (`backend-recon.md`).
- A **fidelity variant** of the build spec that carries the deeper artifacts.

**Out of scope (deferred to Phase B — dynamic analysis):**
- Emulator + `mitmproxy` + `frida` runtime traffic capture. This is the natural
  next increment for true backend-contract fidelity (real requests/responses,
  decrypted payloads, observed screen transitions) and is acknowledged here as
  the planned follow-on, but is **not** part of this spec.

**Hard constraints (unchanged from repo rules):**
- `plugins/android-reverse-engineering/` stays byte-identical. The fidelity mode
  reuses its scripts/skill exactly as the feasibility path does; it adds nothing
  to that tree.
- All new helper scripts are stdlib-only Python or bash 4+, offline-testable
  against `tests/fixtures/`, never hitting the network.
- Working dir stays `./work/{package}/` relative to the user's cwd.

## 3. Honest extraction limits

What a static APK analysis can and cannot recover — stated up front so the spec
does not over-promise:

| Layer | Recoverable statically? | Notes |
|---|---|---|
| Design (colors/fonts/spacing, layouts, drawables, nav) | Yes (native); partial (Compose); poor (Flutter/RN/Unity-il2cpp) | Existing `extract-design.py` + screenshots; fidelity adds per-screen layout trees |
| Screen flow / navigation | Yes (native) | nav XML, Activity/Fragment, Compose NavHost |
| In-app / business logic | Yes (native Kotlin/Java, Unity-mono); medium (Unity-il2cpp); poor (Flutter/RN) | Lives in ViewModels / use-cases / C#; readable after R8 name recovery |
| API contract (endpoints, request/response, auth) | Yes, but only what the client encodes | Static gets the shape; not runtime-observed values |
| **Backend server logic** (DB schema, server-side rules) | **No** | Not in the APK. `backend-recon.md` *infers* a design from the observed contract; marked with confidence, treated as a rebuild target, not stolen code |

The user's chosen targets — **native apps and Unity games** — are precisely the
two where static logic extraction is strongest. Flutter/RN apps fall back to a
`limited:` digest, same as the feasibility path.

## 4. Design

### 4.1 Mode shape

A mode selector resolved in Phase 0:

- `CLONE_APP_MODE=fidelity` environment variable, **or** user intent phrased as
  "detailed clone / replicate in detail / klon planı" → `fidelity`.
- Otherwise → `feasibility` (the existing default; unchanged).

Phase behavior by mode:

| Phase | feasibility (default) | fidelity |
|---|---|---|
| 0 Input | as today | + resolve mode |
| 1 Download | as today | as today |
| 2 RE | shallow (Tier-2 on 3 flows) | **deep** (Tier-2 all first-party + logic + nav + backend recon) |
| 3 Store | metrics + screenshots + iOS check | **screenshots only** (visual ground truth); skip metrics/iOS |
| 4 Stack | choose stack | choose stack (shared — the rebuild target) |
| 5 Effort/Cost | AI-Sprint + infra tables | **skipped** |
| 6 Viability | GO/NO-GO report | **skipped** |
| 7 Decision gate | proceed to plan? | proceed to plan? (shared) |
| 8 Build spec | standard template | **fidelity variant** |

Screenshots are retained in fidelity mode because they are the visual source of
truth for design replication; store metrics, iOS presence, effort, cost, and the
verdict are all feasibility concerns and are dropped.

### 4.2 New and deepened artifacts

All produced by the Phase 2 subagent in its isolated context (so deep extraction
never floods the orchestrator), written under `$WORK/`:

| Artifact | State | Content |
|---|---|---|
| `payloads.json` | deepened | Tier-2 (request/response/headers) for **every first-party endpoint**, not only auth/payment/core. Third-party endpoints stay Tier-1 |
| `logic-digest.md` | **new** | In-app logic & workflows: ViewModel/use-case rules, input validation, state machines, local DB (Room) schema, game formulas. Framework-aware confidence |
| `nav-graph.json` | **new** | Real screen graph from nav XML / Activity-Fragment transitions / Compose NavHost. Nodes = screens, edges = transitions + triggers |
| `backend-recon.md` | **new** | Inferred backend design from the observed contract: entities, relationships, per-endpoint semantics, auth model, probable server-side validation. Every claim confidence-stamped |
| `unity-digest.md` | deepened | Existing type-model + netcode **plus** game mechanics / rules / formulas from C# (mono near-source; il2cpp partial) |

### 4.3 Build-spec fidelity variant

Extends `clone-build-spec-template.md`. Still the single standalone build
contract — a fresh session with it + `$WORK/` rebuilds the clone.

| Section | Fidelity change |
|---|---|
| §3 Screen-by-screen | + per-screen **layout component tree** (from native XML) and the screen's logic (ref `logic-digest.md`), not just a component list |
| §3b User-flow diagrams | **new** — step-by-step flows (onboarding, core loop, payment) from `logic-digest.md` |
| §4 Navigation map | generated from `nav-graph.json`, not inferred |
| §5 API contract | **all** first-party endpoints, full request/response |
| §5b Backend rebuild spec | **new** — the from-scratch backend design (endpoint behavior, auth flow, validation) from `backend-recon.md` |
| §6 Data model | from `backend-recon.md` (entities + relationships + inferred rules) |
| Game variant §3 | scene/prefab spec **plus** game-rule / formula dump |

## 5. Components & files

### 5.1 New helper scripts (`skills/clone-app/scripts/`)

- `extract-logic.py` — walks the decompile root, surfaces logic signals
  (ViewModel/use-case classes, validation calls, state-machine enums + `when`,
  Room `@Entity`/`@Dao`) into a raw feed the subagent distills into
  `logic-digest.md`. Stdlib-only; offline.
- `extract-nav-graph.py` — parses nav XML, Activity/Fragment references, and
  Compose `NavHost` declarations into `nav-graph.json`. Stdlib-only; offline.

### 5.2 New references / rubrics (`skills/clone-app/references/`)

- `fidelity-mode-guide.md` — single source for what the mode skips/adds and the
  branch table; SKILL.md points here rather than duplicating prose.
- `logic-capture-guide.md` — how the subagent distills in-app logic, with
  framework-aware confidence (native/Compose/Unity-mono high–med; Flutter/RN
  low).
- `backend-recon-guide.md` — how to turn the observed contract into an inferred
  backend design, with confidence rules and the "design to rebuild, not stolen
  code" framing.

### 5.3 Changed files

- `SKILL.md` — Phase 0 mode resolution; Phase 2b deep-extraction subagent
  instructions; Phase 3 screenshot-only branch; skip Phase 5/6 in fidelity;
  Phase 8 fidelity-variant selection. Error-handling table gains fidelity rows.
- `re-digest-contract.md` — fidelity adds Tier-2-on-all-first-party and the
  contract for the three new artifacts (`logic-digest.md`, `nav-graph.json`,
  `backend-recon.md`). The existing Tier-2-only-on-3-flows rule stays the
  documented feasibility behavior.
- `clone-build-spec-template.md` — the new/extended sections in §4.3.
- `unity-re-guide.md` — game-mechanic / formula extraction depth.

### 5.4 Untouched

`extract-design.py`, `detect-unity.sh`, `il2cpp-dump.sh`, `unity-assets.sh`,
`download-apk.sh`, store/effort/cost references, and the entire
`android-reverse-engineering` tree. The feasibility path is the default and must
keep working unchanged.

## 6. Testing

Follows the existing pattern: offline fixtures under `tests/fixtures/`, bash
tests with `set -uo pipefail` aggregating failures, stdlib-only Python.

| Test | Verifies |
|---|---|
| `test-extract-logic.py` | Against a fixture decompile tree (1 ViewModel + 1 Room entity + 1 state enum), the expected logic signals are surfaced |
| `test-extract-nav-graph.py` | Against a fixture nav XML + Activity set, the correct node/edge graph JSON is produced |
| `smoke-structure.sh` (update) | New scripts present + executable; new references present; emitted JSON valid |
| `test-skill-content.sh` (new or extended) | SKILL.md contains the mode resolution and the fidelity branch wiring |
| `run-all.sh` (update) | Registers the new suites |

New fixtures: a minimal decompile tree (one ViewModel, one Room entity, one
state enum) and a minimal `navigation/nav.xml` + Activity references. No network.

## 7. Risks & mitigations

- **Token cost of Tier-2-on-all-endpoints.** Mitigated by running it inside the
  Phase 2 subagent's isolated context; only the digest summary returns to the
  orchestrator. The `re-digest-contract.md` warning about token cost applies to
  the feasibility path and is explicitly overridden only in fidelity mode.
- **Over-promising backend fidelity.** Mitigated by confidence-stamping every
  inference in `backend-recon.md` and framing it as a rebuild target, not
  recovered server code (§3).
- **Flutter/RN low yield.** Same `limited:` framework guard as today; the
  fidelity digest says so and leans on screenshots + whatever signals exist.
- **Legal.** The existing legal note in SKILL.md still governs; fidelity mode
  does not change the authorization requirement and the same "recreate in style,
  treat extracted assets as reference" stance applies.

## 8. Deferred follow-on (Phase B)

Dynamic analysis — emulator + `mitmproxy` (real traffic) + `frida` (runtime
hooks, decrypted payloads, observed transitions) — is the planned next increment
for true runtime-observed workflow and backend fidelity. It will land as its own
spec once the static deep-extraction mode in this spec is in place.
