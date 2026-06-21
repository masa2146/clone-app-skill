---
description: Analyze a Google Play app to assess cloning it — download the APK, reverse engineer the tech stack and APIs, analyze app-store presence, estimate AI-assisted build effort and infrastructure cost, judge market viability, and optionally generate an implementation plan. Use when the user gives a Google Play URL or package name and wants a clone feasibility analysis, effort estimate, or tech-stack breakdown. 中文触发词：克隆应用、复刻这个app、分析可行性、估算开发量、克隆可行性分析
trigger: clone app|clone this app|clone feasibility|feasibility analysis|estimate effort to build|reverse engineer and clone|analyze this play store app|can I clone|克隆应用|复刻|可行性分析
---

# Clone App — Feasibility & Effort Analysis

Take a Google Play URL (or package name), reverse engineer the app, analyze its
market, estimate AI-assisted clone effort and infrastructure cost, and produce a
viability report. If the user approves, hand off to the writing-plans skill to
generate a full implementation plan.

This skill orchestrates 8 phases. Deterministic steps are factored into helper
scripts under `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/`. Reverse
engineering reuses the sibling `android-reverse-engineering` plugin's scripts.

## Legal note
Only analyze apps you are authorized to (your own, or for lawful interoperability
/ research). Surface this to the user if intent is unclear. Do not proceed for
clearly infringing intent.

## Phase 0: Input & Validation

Extract the package name:
```bash
PKG="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/extract-package.sh "<user-input>")"
```
If it exits non-zero, ask the user for the package name directly, then re-run.

Create the working dir: `WORK="./work/$PKG"` and `mkdir -p "$WORK"`.

## Phase 1: APK Download

```bash
APK="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/download-apk.sh "$PKG" "$WORK")"
```
The script downloads from APKCombo (the old APKPure direct endpoint is now behind
a Cloudflare bot challenge), retries 3×, and prints the path (`app.apk` or
`app.xapk`). If it exits non-zero, the app may not be on APKCombo or the page
format changed — tell the user the download failed and ask for a local APK/XAPK
path; set `APK` to that path.

## Phase 2: Reverse Engineering

Resolve the sibling RE scripts:
```bash
RE="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/resolve-re-scripts.sh)"
```
If it exits non-zero, show its error (RE plugin not installed) and stop. If it
prints a `WARNING:` about bash version, the RE scripts need **bash 4+** (macOS
ships 3.2; their `${VAR,,}` syntax fails as "bad substitution" otherwise) —
install one with `brew install bash` before continuing, then re-run Phase 2.

Run, in order, reading each output before the next:
1. `bash "$RE/fingerprint.sh" "$APK"` — framework, HTTP stack, obfuscation, SDKs, native libs.
   - **If framework is Flutter / React Native / Cordova / Xamarin:** tell the user Java
     decompilation is limited; proceed but rely on manifest + strings + hardcoded URLs +
     the fingerprint SDK list. Skip steps 3-5's deep API extraction expectations.
2. `bash "$RE/check-deps.sh"` — parse `INSTALL_REQUIRED:` / `INSTALL_OPTIONAL:` lines.
   Install required deps with `bash "$RE/install-dep.sh" <dep>`; re-run check-deps until clean.
   Ask the user before installing optional deps (vineflower, dex2jar).
3. `bash "$RE/decompile.sh" -o "$WORK/output" "$APK"` (add `--deobf` if fingerprint showed heavy obfuscation: `bash "$RE/decompile.sh" -o "$WORK/output" --deobf "$APK"`).
   Sources land at `$WORK/output/sources/`.
4. If the app is Kotlin: `bash "$RE/recover-kotlin-names.sh" "$WORK/output/sources" "$WORK/output/names/"`.
5. `bash "$RE/find-api-calls.sh" "$WORK/output/sources"` (full scan; add `--ktor`/`--apollo`/`--paths` as
   the fingerprint suggests).

From these outputs assemble: framework, HTTP stack, **API endpoint list**,
first-party vs third-party hosts, AndroidManifest summary (permissions, components),
and a **feature list** (screen count, SDKs, backend signals). Keep this in context
for later phases.

## Phase 3: Store Analysis

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/scrape-play-store.py "$PKG" > "$WORK/play.json"
```
Read `play.json` for rating, rating_count, installs, category, developer, updated.
Use the `title` to check iOS:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/check-appstore.py "<title>" > "$WORK/appstore.json"
```
If Play scrape returned mostly nulls (page layout changed), fall back to a web
search for the app's metrics and note the source. App Store absence is fine —
continue with Google Play data only.

## Phase 4: Stack Recommendation

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/stack-recommendation-guide.md`.
Using the RE results + store data, present 2-3 stack options as a table and ask
the user to choose. **Wait for the user's choice before Phase 5.** Lock it.

## Phase 5: Effort & Cost Estimation

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/effort-estimation-guide.md`
and `infra-cost-guide.md`. Build:
- the feature list → AI-Sprint effort table (min-max total, uncertainty band),
- the MVP/Growth/Scale monthly infra cost table.
Base both on the **user-selected stack** from Phase 4.

## Phase 6: Market Viability Report

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/report-template.md`.
Fill every section from the data gathered. For market analysis (competitors,
market size), use web search as needed. Produce a GO / CONDITIONAL GO / NO GO
verdict tying effort + cost against market opportunity.

Write the report:
```
$WORK/clone-report-<YYYY-MM-DD>.md
```
(Use the actual run date.) Show the user a concise summary + the verdict.

## Phase 7: Decision Gate

Ask: "Report saved to `$WORK/clone-report-<date>.md`. Proceed to build the
implementation plan?"
- **Yes** → invoke the `superpowers:writing-plans` skill, passing the report as
  context (the selected stack, feature list, and effort table become the plan's spec).
- **No** → stop; the report stands on its own.

## Error Handling Summary
| Scenario | Action |
|---|---|
| Package not in URL | ask user for package name |
| Download fails 3× | ask for local APK path |
| RE plugin missing | show resolver error, stop |
| Flutter/RN/Cordova/Xamarin | warn, continue with limited RE |
| App Store not found | continue Google Play only |
| Play scrape returns nulls | web-search fallback, note source |
| Heavy obfuscation | add uncertainty band, note in report |
| writing-plans unavailable | write the plan as Markdown manually |
