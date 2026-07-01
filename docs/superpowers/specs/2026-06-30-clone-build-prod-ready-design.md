# clone-build — Spec-to-Prod-Ready Build & Verify Stage — Design Spec

**Date:** 2026-06-30
**Status:** Approved (brainstorming complete)
**Scope:** One new plugin (`clone-build`) that turns a `clone-build-spec.md` +
`$WORK/` artifacts into running, verified, production-ready code — for **games**
(via Unity MCP) or **apps** (Flutter / native Android / RN). Removes the never-built
`hermes-build` plugin from the pipeline and takes its Phase-7 slot. Plus small edits to
`clone-app` (Phase 7 + spec template §11), root `marketplace.json`, and the umbrella
pipeline spec.

## 1. Purpose

Close the pipeline's last gap: today `clone-app` ends at a spec + `superpowers:writing-plans`.
No stage actually **builds and verifies** the clone. `clone-build` is that stage.

Goal: from the standalone build contract, produce prod-ready code such that **a weak LLM
in an independent, fresh session — given the right task brief and gates — still converges
on correct, verified output.** Robustness is *structural* (fresh subagent per task +
machine-checkable gates), not a matter of trusting the model to self-judge.

Pipeline becomes: **`market-research → clone-app → clone-build`**.

Effort stays measured in **AI Sprints** (one focused session), never calendar time —
consistent with the rest of the project.

## 2. The hard constraint (unchanged)

`plugins/android-reverse-engineering/` stays byte-identical to upstream. Before any commit:

```bash
git status --porcelain plugins/android-reverse-engineering/   # must print nothing
```

All new work lives under `plugins/clone-build/`. Shared/existing edits, minimal:
- `clone-app/skills/clone-app/SKILL.md` — Phase 7 decision gate (rewire third branch).
- `clone-app/skills/clone-app/references/clone-build-spec-template.md` — add §11 "Build readiness".
- root `.claude-plugin/marketplace.json` — add `clone-build`; remove any `hermes-build` entry.
- `docs/superpowers/specs/2026-06-22-market-to-build-pipeline-design.md` — §8 / build-order edits
  reflecting `hermes-build` removal and `clone-build` replacement.

## 3. Decisions locked in brainstorming

| # | Decision | Choice |
|---|----------|--------|
| Core goal | What to build | Build+verify stage **and** weak-LLM-robust plan format, as one pipeline |
| Build runtime | Games vs apps | **One stage, two branches.** Shared flow in `SKILL.md`; game/app specifics in separate reference files loaded on demand (token-lean). |
| Forcing function | Reach prod-ready under weak model | **All three layered:** executable gates (backbone) + TDD (logic) + visual-diff loop (UI). |
| vs hermes-build | Relationship | **Replace it.** `hermes-build` removed entirely from the design. `clone-build` takes Phase 7's build branch. Firebase/ads/Play-publish are out of scope (optional future). |
| Unity bootstrap | Get a Unity project | **Scaffold via Unity CLI headless, then drive** via MCP. Preflight detects connection; guides + pauses if absent. |
| App verify | Run + check app build | **Tiered:** always-on hard gate (compile + test + install + launch-no-crash); visual gate (adb screencap vs target screenshots) when an emulator/device is present, else SKIP + guidance. Never half-fails. |
| Packaging | Where it lives | **New plugin `plugins/clone-build/`**, mirroring existing layout. |
| Plan source | Who makes the robust plan | **clone-build owns plan generation** (strict, template-driven, deterministic). **Execution reuses** `superpowers:subagent-driven-development` (proven fresh-subagent-per-task loop). |
| Loop architecture | How tasks run | **Approach B** — per-task self-contained brief + machine gate; one task = one screen/flow/endpoint-group/scene; reviewer subagent checks gate evidence before unblocking dependents. |

## 4. Architecture

```
plugins/
  android-reverse-engineering/   [upstream, untouched]
  market-research/               [existing]
  clone-app/                     [existing — Phase 7 rewire + spec §11]
  clone-build/                   [NEW]
```

**Pipeline (chained handoffs, no central orchestrator):**

```
clone-app  (existing 8 phases)
   → Phase 7 decision gate:
       • "Build it"   → invoke clone-build   (NEW — replaces hermes-build slot)
       • "Plan only"  → superpowers:writing-plans   (existing)
       • "No"         → stop
clone-build
   → P0 preflight + spec load + branch detect (game|app)
   → P1 scaffold buildable project (Unity CLI | flutter/gradle/RN)
   → P2 generate build-plan.json (task graph, gate per task)
   → P3 execute via subagent-driven-development (fresh subagent + gate + reviewer per task)
   → P4 integration verify (full build + launch + end-to-end visual pass)
   → P5 build-report-<date>.md
```

**Input contract (the whole interface):** `clone-build` consumes exactly what `clone-app`
Phase 8 produces — `$WORK/clone-build-spec.md` + the `$WORK/` artifacts (`design-tokens.json`,
`payloads.json`, `nav-graph.json`, `logic-digest.md`, `screenshots/`, `unity-digest.md` /
`game-assets/` for Unity). No new extraction; `clone-build` is stateless w.r.t. clone-app internals.

## 5. Plugin: `clone-build`

### 5.1 Skill structure — shared spine + on-demand branch references

`skills/clone-build/SKILL.md` is the **shared spine only** (token-lean). Branch detail lives
in references loaded on demand, so a weak model loads the spine + **one** branch guide, never both.

**Phases (SKILL.md):**

- **P0 — Preflight & spec load.** Read `clone-build-spec.md`; detect branch via
  `detect-branch.sh` → `game | app` (+ sub-stack). Probe toolchain via `preflight.sh` →
  `preflight.json`. Load the matching branch reference. Run **spec-completeness check**
  (see §7.1): missing/low-confidence sections become `needs-human-input` tasks, not silent guesses.
- **P1 — Project scaffold.** Branch-specific. Produces an empty **buildable** project.
- **P2 — Plan generation.** `gen-build-plan.py`: spec + artifacts → `build-plan.json` + per-task
  briefs. Deterministic (no clock/random). Gate *kind* per task from `gate-catalog.md`.
- **P3 — Execution loop.** Invoke `superpowers:subagent-driven-development` over the plan:
  per task → fresh subagent → implement → run its gate → reviewer checks evidence → unblock dependents.
- **P4 — Integration verify.** Full build + launch + end-to-end visual pass over all screens/scenes.
- **P5 — Build report.** `build-report-<YYYY-MM-DD>.md`: tasks done, gates passed, visual-diff
  results, SKIPs + why, next manual steps.

**References (`references/`, loaded on demand):**
- `game-build-guide.md` — Unity CLI scaffold; unity-mcp driving (delegates tool detail to the
  existing `unity-mcp-skill`, with a minimal inline fallback); scene/prefab tasks; `manage_camera`
  screenshot gate; `run_tests` TDD gate.
- `app-build-guide.md` — Flutter/native/RN scaffold; gradle/flutter build; emulator + `adb screencap`
  gate; nav-graph-driven screen navigation.
- `plan-contract.md` — task-graph schema + the forcing rule (branch-agnostic).
- `gate-catalog.md` — gate kinds with exact command shape + pass condition.
- `build-report-template.md`.

### 5.2 Scripts (`scripts/`, independently testable, stdlib-only Python / `#!/usr/bin/env bash`)

- `detect-branch.sh` — spec → `game|app` (+ sub-stack). Mirrors `detect-unity.sh` style.
- `scaffold-unity.sh` — resolve Unity (Hub default paths, `$UNITY_PATH`), headless
  `-batchmode -quit -createProject`, inject MCP-for-Unity package, print "open + connect MCP".
- `scaffold-app.sh` — branch on stack: `flutter create` | gradle template | `react-native init`;
  inject deps from spec §5.
- `gen-build-plan.py` — `clone-build-spec.md` + artifacts → `build-plan.json` + briefs.
  Deterministic; fixture-tested offline. Includes the spec-completeness check.
- `run-gate.sh` — dispatch a gate by kind (`build|tdd|visual-diff|launch-crash`) → exit 0/non-0 +
  evidence to stdout. The single chokepoint the executor and reviewer both call.
- `preflight.sh` — probe Unity / Flutter / gradle / adb / emulator → `preflight.json`.

### 5.3 State (user cwd, never inside the plugin)

Under the existing `./work/<pkg>/` from clone-app, `clone-build` adds:
- `clone/` — the scaffolded project (Unity project or app project).
- `build-plan.json` — task graph with per-task status (enables **resume**).
- `preflight.json` — capability probe.
- `build-report-<date>.md`.

## 6. The robustness core — task graph + gate contract

Plan generation (P2) emits **`build-plan.json`**: ordered, self-contained tasks. One task =
one screen, one user flow, one endpoint group, or one game scene.

**Task schema:**
```json
{
  "id": "screen-login",
  "type": "ui | logic | api | scene | integration",
  "title": "Build Login screen",
  "inputs": ["<abs path: spec §3 login entry>", "$WORK/screenshots/03.png",
             "$WORK/design-tokens.json", "$WORK/logic-digest.md#login"],
  "instructions": "<concrete, unambiguous steps>",
  "gate": { "kind": "visual-diff", "command": "...", "pass_when": "..." },
  "status": "pending | done",
  "depends_on": ["scaffold", "design-system"]
}
```

**Gate catalog** — every task carries exactly one machine-checkable gate; kind by task type:

| Task type | Gate kind | Pass condition |
|---|---|---|
| logic / formula | **TDD** | failing test written first, then `<test cmd>` exits 0 |
| api / data model | **TDD** | contract test vs `payloads.json` shape exits 0 |
| ui (app) | **visual-diff** | `adb exec-out screencap` vs `screenshots/NN.png`, model judges match ≥ threshold; **plus** build + launch no-crash |
| ui / scene (game) | **visual-diff** | `manage_camera(action="screenshot")` vs `screenshots/NN.png`, model judges match |
| any | **build** | compiles, 0 errors (`read_console` / gradle exit 0) |
| integration | **launch-crash** | app/scene starts, no fatal in logcat/console for N seconds |

**The forcing rule** (written into every brief + enforced by the executor): *a subagent may not
report a task done until its gate command has run and the pass condition is met.* Gate evidence
(test result, console scan, screenshot + verdict) is pasted into the task report. The reviewer
subagent re-checks the evidence before unblocking dependents. No evidence → task stays open.

This realizes the layered forcing function: **build gate** (backbone) on every task, **TDD** on
logic/api, **visual-diff** on UI — assigned by type, never optional. The model never self-certifies
"looks done"; a command exits 0 or it doesn't. Fresh subagent per task = no context drift; reviewer
= second check on evidence. This is the same `subagent-driven-development` pattern this very repo
was built with (`.superpowers/sdd/`).

## 7. Branch detail

### 7.1 Spec-completeness preflight (both branches)

Before building, `gen-build-plan.py` validates the spec carries what a buildable plan needs
(design tokens present, payloads non-empty, screenshots exist, nav-graph present). Missing or
low-confidence sections produce a **gap list**; affected tasks are marked `needs-human-input`
rather than generating code on a hole. Structured input for this comes from the new spec
template **§11 "Build readiness"** (clone-app edit) — explicit high/low-confidence flags.

### 7.2 Game branch (Unity MCP)

- **Scaffold (`scaffold-unity.sh`):** resolve Unity Editor (Hub defaults, `$UNITY_PATH`,
  version from spec else latest LTS). Headless `-createProject`, inject
  `com.coplaydev.unity-mcp`. Print exact "open project + confirm MCP connected" step.
  **Preflight gate:** poll `mcpforunity://editor/state` until `ready_for_tools == true`;
  if no connection after guidance → **pause** (best-effort convention, never half-fail).
- **Driving (P3), reusing `unity-mcp-skill` patterns:** resource-first (read `editor/state`,
  `scene/gameobject-api`, `project/info` before acting). `create_script` / `script_apply_edits`
  for C# (mechanics/formulas from `unity-digest.md`) → wait `is_compiling==false` →
  `read_console(types=["error"])` = **build gate**. `manage_gameobject` / `manage_components` /
  `manage_prefabs` (+ `batch_execute` for bulk) for scenes from the type/scene model.
  `manage_camera(action="screenshot", include_image=True)` vs `screenshots/NN.png` =
  **visual-diff gate**. `run_tests` (Unity Test Framework) = **TDD gate**.
- **Dependency posture:** `game-build-guide.md` delegates tool schemas to `unity-mcp-skill`
  (keeps clone-build lean + version-resilient); carries a minimal inline fallback (the ~5 tools
  above) if that skill is absent.
- **Assets:** `game-assets/manifest.json` is reference. The unity-re-guide legal note carries
  forward — recreate in-style for unauthorized use; extracted assets reference-only. Build report restates it.

### 7.3 App branch (Flutter / native Android / RN)

- **Scaffold (`scaffold-app.sh`):** branch on the spec's selected stack — `flutter create` |
  `gradle init`/template | `npx react-native init`. Inject deps from spec §5. Toolchain preflight
  (`flutter doctor` / `gradle -v` / node) → `preflight.json`; missing → guidance + pause.
- **Gates (tiered):**
  1. **Always-on hard gate (no display needed):** `<build cmd>` exits 0 → unit/contract tests
     pass → `adb install` → `adb shell am start` → no fatal in `logcat` for N seconds. Weak model can't skip.
  2. **Visual gate (when a device/emulator is present):** preflight probes `adb devices`;
     if up → `adb exec-out screencap -p` per screen → compare to `screenshots/NN.png` → iterate.
     If absent → print exact `emulator -avd <name>` / device steps; if user skips → mark visual
     **SKIP**, hard gate still enforced. Never blocks.
- **Navigation-driven screenshots:** use `nav-graph.json` to script `adb shell input` taps to
  reach each screen deterministically before screencap — scripted nav, not weak-model guesswork.

Both branches share the shape **build → run → screenshot → compare**; only the driver differs
(unity-mcp vs adb).

## 8. Error handling (SKILL.md table)

| Scenario | Action |
|---|---|
| Spec/artifacts missing | stop; tell user to run clone-app Phase 8 first |
| Unity not found | print Hub install guidance, pause |
| MCP not connected after scaffold | guidance, poll `editor/state`, pause |
| Gate fails | task stays open; subagent retries; after N retries escalate to user with evidence |
| Visual-diff below threshold | iterate (re-edit → re-shot) up to N; then flag for user review, never force-pass |
| Emulator absent (app) | hard gate still runs; visual = SKIP + guidance |
| Toolchain missing (flutter/gradle/node) | guidance, pause |
| `unity-mcp-skill` absent | fall back to inline tool subset in `game-build-guide.md` |
| `subagent-driven-development` unavailable | fall back: run tasks inline, still call `run-gate.sh` per task |
| Mid-run session death | resume from `build-plan.json` status — skip done-and-gated tasks |

## 9. Cross-cutting conventions (inherited)

- **Working dir** is `./work/<pkg>/` relative to the user's cwd — never inside any plugin.
- **Scripts** use `#!/usr/bin/env bash`, run via `bash <path>`; Python is **stdlib-only**
  (`urllib`, `json`, `re`); no pip, no virtualenv. bash 4+ at runtime (project note).
- **Determinism:** `gen-build-plan.py` takes no clock/random → same spec = same plan
  (testable against fixtures), like `history.py` in market-research.
- **Tests** use `set -uo pipefail`, aggregate failures, exit non-zero if any fail. No live
  Unity / emulator / network — fixtures only. New logic needs a fixture, not a live call.
- **Commits** Conventional, scoped: `feat(clone-build): …`, `test(clone-build): …`.
- **Marketplace:** add `clone-build` to root `.claude-plugin/marketplace.json`; each plugin
  carries its own `.claude-plugin/plugin.json`.

## 10. Tests (`tests/`)

- `test-detect-branch.sh` — sample specs → `game|app`.
- `test-gen-build-plan.py` — fixture spec → expected `build-plan.json` (incl. gap-list path).
- `test-run-gate.sh` — mock each gate kind pass/fail.
- `test-preflight.sh` — mock present/missing toolchains.
- `test-skill-phases.sh` — phase markers + handoff strings present in SKILL.md.
- `test-references-content.sh` — branch guides + gate-catalog carry required keys.
- `smoke-structure.sh` — files present, scripts executable, JSON valid, plugin in marketplace.
- `run-all.sh` — aggregates.

## 11. Build order (each gets its own implementation plan via writing-plans)

1. **`clone-build` skeleton** — plugin layout, `SKILL.md` spine, `plan-contract.md` +
   `gate-catalog.md`, `gen-build-plan.py` + `run-gate.sh` + `detect-branch.sh` + `preflight.sh`
   + their tests. Branch-agnostic core, standalone-testable with fixtures.
2. **App branch** — `scaffold-app.sh`, adb gates, `app-build-guide.md`; prove the loop end-to-end
   on a small real spec. (Fewer prereqs than Unity → prove the loop first.)
3. **Game branch** — `scaffold-unity.sh`, unity-mcp driving, `game-build-guide.md`.
4. **Wiring** — clone-app Phase 7 rewire, spec template §11, `marketplace.json` (add clone-build,
   remove hermes-build), umbrella-spec §8/build-order edits.

## 12. Out of scope

- Firebase / AdMob / Play Console publishing (the old hermes-build remit) — removed, optional future.
- `hermes-agent` dependency — dropped.
- iOS build (Android/Unity only).
- Paid services; any irreversible publish action.
- Modifying the upstream `android-reverse-engineering` plugin.
- Bootstrapping the user's Unity / emulator / toolchains (best-effort detect + guide only).
