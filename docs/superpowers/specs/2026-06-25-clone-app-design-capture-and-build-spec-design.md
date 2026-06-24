# clone-app: Design Capture + Standalone Build Spec (+ Unity/Game Support)

**Date:** 2026-06-25
**Status:** Approved (design)
**Plugin:** `plugins/clone-app/`

## Problem

The `clone-app` skill produces a feasibility report and, on approval, hands off to
`superpowers:writing-plans`. Three gaps make the resulting plan insufficient for
actually building a production-ready clone:

1. **No design / UI-UX capture.** The RE digest captures framework, hosts,
   endpoints, payloads, secrets, and feature *signals* (screen count, SDKs,
   permissions). Nothing visual is captured: no colors, typography, spacing,
   theme, layout, navigation map, or screenshots. The report's "Feature List" is
   just a screen count + endpoint count. The design system of the target app is
   present in the decompiled APK and on the Play listing, but it is thrown away.

2. **The plan is not standalone.** Phase 7 passes `writing-plans` only the thin
   feasibility report (stack, feature list, effort table). A fresh session
   executing that plan has no description of what the app looks like or how each
   screen behaves, so the clone ends up missing most features and looking wrong.

3. **Not production-ready.** No screen-by-screen spec, no asset inventory, no
   acceptance criteria — nothing that defines "done" for a prod-quality clone.

4. **Unity games are unsupported.** Unity apps compile game logic into
   `libil2cpp.so` (IL2CPP) or ship it as `Managed/*.dll` (Mono). jadx is blind to
   IL2CPP — it only decompiles the thin Unity bootstrap Java, so a Unity game
   currently produces an empty/useless digest. The existing framework guard does
   not even list Unity. Game art assets (the design system equivalent for games)
   are never extracted.

## Goal

Make `clone-app` capture enough design + feature + API + asset detail that the
generated implementation plan is **standalone**: a fresh Claude Code session,
given only the build spec and the `./work/<pkg>/` artifacts, can build a
**pixel-perfect, production-ready** clone.

User decisions driving this design:
- **Clone target = pixel-perfect visual copy** (same colors, typography, layout,
  icons, screen flow), not "functional clone with our own design".
- **Visual reference source = Play Store screenshots + APK resource extraction**
  (no emulator-driven screen capture).
- **Standalone delivery = a dedicated comprehensive "Clone Build Spec" artifact**
  that feeds `writing-plans` (not a bloated feasibility report, not relying on
  the plan tasks alone).
- **Games (Unity) are in scope**: IL2CPP via Il2CppInspectorRedux, Mono via
  ILSpy, and game-asset extraction via AssetRipper.

## Hard constraint (unchanged)

`plugins/android-reverse-engineering/` is vendored upstream and MUST stay
byte-identical (`git status --porcelain plugins/android-reverse-engineering/`
prints nothing). All new logic — including Unity/IL2CPP handling — lives in
`plugins/clone-app/`. clone-app already orchestrates the RE plugin's scripts, so
the Unity path is a clone-app-side branch that runs *instead of / in addition to*
jadx when the fingerprint is Unity.

## Architecture

The skill keeps its scripts-for-deterministic / rubrics-for-judgment split and
its "RE runs in an isolated subagent so decompiled sources never flood the
orchestrator context" pattern. Design extraction and Unity handling reuse that
same isolation: the Phase 2 subagent already holds the decompiled tree, so it
extracts the design tokens and Unity data there and returns only digests +
summaries.

### Data flow (additions to the existing 8-phase flow)

- **Phase 2 (RE subagent) — extended.**
  - After decompile, the subagent detects Unity (`detect-unity.sh`) and branches:
    - **Standard (jadx) apps:** unchanged RE workflow, *plus* runs
      `extract-design.py "$WORK/output"` → writes `design-tokens.json` +
      `design-digest.md`.
    - **Unity IL2CPP:** runs `il2cpp-dump.sh` (Il2CppInspectorRedux on
      `libil2cpp.so` + `global-metadata.dat`) → C# type model; runs
      `unity-assets.sh` (AssetRipper) → `game-assets/`. Writes `unity-digest.md`.
    - **Unity Mono:** runs `ilspycmd` on `Managed/*.dll` → C# sources; runs
      `unity-assets.sh`. Writes `unity-digest.md`.
  - Subagent returns the existing `re-summary.txt` plus a short `design-summary`
    (and, for Unity, a `unity-summary`) and the artifact paths — never raw
    sources/assets.
- **Phase 3 (Play scrape) — extended.** `scrape-play-store.py` additionally emits
  `screenshot_urls`, `feature_graphic`, and the full `description`. The skill
  downloads the screenshots inline (curl loop) to `$WORK/screenshots/*.png` and
  writes `screenshots/manifest.json`.
- **Phase 6 (report) — extended.** Report-template gains a "Design System" summary
  and a "Game Assets" section (when Unity).
- **Phase 7 (decision gate) — unchanged** ("proceed to build plan?").
- **Phase 8 (NEW) — Clone Build Spec assembly.** On "yes", before invoking
  `writing-plans`, the skill assembles `$WORK/clone-build-spec.md` from all
  artifacts, then invokes `writing-plans` with that spec as the input.

### New / changed scripts (`plugins/clone-app/skills/clone-app/scripts/`)

| Script | Status | Responsibility |
|---|---|---|
| `extract-design.py` | new | Parse decompiled `res/` → `design-tokens.json` + `design-digest.md`. Reads `values/colors.xml`, `dimens.xml`, `styles.xml`+`themes.xml`, `font/` dir, `mipmap*`/`drawable*` inventory, counts `layout/*.xml`. Framework-aware: native = rich; Compose = res values + grep Kotlin for `Color(0x…)` / `.dp`; Flutter/RN = low confidence, lean on screenshots. Each token group tagged confidence high/med/low. Stdlib-only. |
| `scrape-play-store.py` | changed | Add `screenshot_urls`, `feature_graphic`, full `description` to the JSON output. |
| `detect-unity.sh` | new | Inspect APK/XAPK zip entries for Unity markers → prints `il2cpp` \| `mono` \| `none`. (`libil2cpp.so` + `…/Metadata/global-metadata.dat` ⇒ il2cpp; `…/Managed/*.dll` ⇒ mono.) |
| `il2cpp-dump.sh` | new | Thin wrapper around Il2CppInspectorRedux CLI (args: `libil2cpp.so`, `global-metadata.dat`, out dir). Missing tool ⇒ clear install guidance + non-zero exit (caller degrades). |
| `unity-assets.sh` | new | Thin wrapper around AssetRipper CLI (args: apk, out dir). Missing tool ⇒ graceful guidance + non-zero exit. |

Mono decompile uses `ilspycmd` directly from the subagent (no dedicated wrapper
needed; one command).

### New artifacts (under `./work/<pkg>/`)

| Artifact | Producer | Contents |
|---|---|---|
| `design-tokens.json` | `extract-design.py` | colors, typography, spacing/dimens, corner/shape, fonts, light/dark theme, icon ref, layout inventory; each group has a `confidence`. For Unity, filled with asset inventory + scene/prefab structure instead. |
| `design-digest.md` | `extract-design.py` | Human-readable design system. |
| `screenshots/*.png` + `manifest.json` | Phase 3 | Downloaded Play screenshots + index (url, local path, order). |
| `unity-digest.md` | Phase 2 (Unity branch) | C# type model (class/method/field/enum signatures), detected netcode (Photon/PlayFab/Mirror/custom), data model. |
| `game-assets/` + `manifest.json` | `unity-assets.sh` | Extracted textures/sprites/UI atlases/fonts/audio/shaders/scenes/prefabs + inventory. |
| `clone-build-spec.md` | Phase 8 | The comprehensive standalone build spec (below). |

### Clone Build Spec (`clone-build-spec.md`) — the core deliverable

App variant sections:
1. Product overview + target parity definition.
2. Design system — from `design-tokens.json`: color palette, typography,
   spacing/dimens, corner/shape, iconography, light/dark.
3. **Screen-by-screen spec** — per screen: purpose, layout, components, states
   (empty/loading/error), navigation, matching screenshot reference
   (`screenshots/NN.png`).
4. Navigation map / IA.
5. Full API contract — from `payloads.json`: endpoint, auth, request/response
   shape.
6. Data model.
7. Asset inventory — icon/font/drawable (extract or recreate).
8. **Acceptance criteria** — per screen + per flow (the prod-ready bar).
9. Out of scope / assumptions.
10. References to `$WORK/` artifacts — **absolute paths + summaries**, so a fresh
    session can locate everything.

Game variant differences:
- §3 is scene/prefab-based instead of screen-based.
- §5 is netcode (Photon/PlayFab/Mirror/custom) instead of REST.
- §7 is the game-asset inventory (sprites/atlases/audio/shaders) + the
  AssetRipper project path; §2 is art-style + UI atlas.

**Standalone guarantee:** the spec references every `$WORK/` artifact by absolute
path *and* embeds a summary, so the build session needs only the spec + `$WORK/`.

### New / changed references (`plugins/clone-app/skills/clone-app/references/`)

| File | Status | Purpose |
|---|---|---|
| `design-capture-guide.md` | new | What tokens to extract and how; framework-aware reading (native XML / Compose-Kotlin / Flutter-RN / Unity); confidence tiers; how Play screenshots fill gaps. |
| `unity-re-guide.md` | new | IL2CPP vs Mono; tool install (Il2CppInspectorRedux, ilspycmd, AssetRipper); what is / isn't recoverable (IL2CPP gives signatures + structure, not method bodies); graceful degradation. |
| `clone-build-spec-template.md` | new | The build-spec structure above (app + game variants). |
| `re-digest-contract.md` | changed | Add the design + unity files to the subagent's required outputs and return value. |
| `report-template.md` | changed | Add "Design System" + "Game Assets (if Unity)" summary sections. |

### SKILL.md changes

- Phase 2: add design-extraction step (standard branch) and the Unity detect →
  IL2CPP/Mono branch; widen the framework guard to include Unity with
  `RE Method: limited: unity-no-tools` when the external tools are absent.
- Phase 3: download screenshots from the scraped URLs into `$WORK/screenshots/`.
- Phase 6: fill the new report sections.
- Phase 8 (new): assemble `clone-build-spec.md`, then invoke `writing-plans` with
  it.
- Strengthen the legal gate (game art is copyrighted; the spec recreates in the
  same style and treats extracted assets as reference, not ship-ready, outside
  authorized use).
- Error-handling table: Unity tools missing ⇒ limited digest + continue.

## External tool reality

Il2CppInspectorRedux, AssetRipper, and ILSpy are .NET-based — not `brew`
one-liners. The forced approach: the skill **detects** Unity, **drives** these
external tools when present, otherwise prints install guidance and degrades to a
partial digest (same pattern as the existing Flutter/RN framework guard).
Tools and references:
- IL2CPP RE: Il2CppInspectorRedux — https://github.com/LukeFZ/Il2CppInspectorRedux
- Unity asset extraction: AssetRipper (CLI)
- Mono `.dll` decompile: `ilspycmd` (ILSpy CLI)

## Testing

Stdlib-only Python, offline fixtures, bash tests with `set -uo pipefail` +
aggregated `fail` var (existing pattern).

- `test-extract-design.py` — fixture `res/` (colors/dimens/themes/font) →
  assert tokens parsed.
- `test-detect-unity.sh` — fixture zips with il2cpp / mono / none markers →
  assert correct classification.
- `test-scrape-play-store.py` — add `screenshot_urls` assertion; update fixture.
- `il2cpp-dump.sh` / `unity-assets.sh` — test only the "tool missing ⇒ graceful
  non-zero + guidance" path (binary/network-heavy paths not exercised).
- `smoke-structure.sh` + `run-all.sh` — new files present + executable.

## Out of scope

- Emulator-driven screen capture (decided against; Play screenshots + APK
  resources only).
- The future `hermes-build` plugin and the Phase 7 "Build with hermes" branch.
- Bundling the .NET tools; they remain external dependencies with install
  guidance.
- iOS design/asset extraction (App Store check stays presence-only).

## Legal

Pixel-perfect cloning and especially extracting copyrighted game art are
high-risk. The skill's legal gate is strengthened: proceed only for authorized
use (own app, lawful interoperability/research); the build spec recreates assets
in the same style and treats extracted assets as reference, not ship-ready,
outside authorized contexts.
