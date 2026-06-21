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
The script downloads via `apkeep` (default source `apk-pure`; no auth, no
JavaScript, handles XAPK split bundling) and prints the path (`app.apk` or
`app.xapk`). It needs the `apkeep` binary on PATH — install with
`brew install apkeep` (or `cargo install apkeep`). If it exits non-zero,
`apkeep` may be missing or the app isn't on that source (try another with
`CLONE_APP_APKEEP_SOURCE=apk-combo`) — tell the user the download failed and
ask for a local APK/XAPK path; set `APK` to that path.

## Phase 2: Reverse Engineering (probe → dispatch → consume)

RE runs inside an **isolated subagent** so the decompiled sources never flood
this orchestrator's context. The subagent prefers the
`android-reverse-engineering` **skill** and falls back to that plugin's bash
**scripts**. Either way it writes the same digest files to `$WORK/`, defined
in `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/re-digest-contract.md`.

### Phase 2a — Probe

```bash
RE="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/resolve-re-scripts.sh 2>/tmp/re-err)"; RC=$?
```
- `RC == 0` → the RE **scripts** are on disk (fallback is available). If it
  printed a `WARNING:` about bash version, the scripts need **bash 4+**
  (macOS ships 3.2; `${VAR,,}` fails as "bad substitution") — install one with
  `brew install bash` before the script-fallback branch can succeed.
- Check your own available-skills list for `android-reverse-engineering` →
  is the RE **skill** registered?

Pick the branch:

| RE skill registered | RE scripts on disk (`RC`) | Branch |
|---|---|---|
| yes | any | **re-skill** |
| no | 0 | **direct-scripts** |
| no | 1 | **stop** — show the `/tmp/re-err` resolver error and halt |

### Phase 2b — Dispatch the subagent

Dispatch one subagent (Agent tool, `general-purpose` type — it can both invoke
skills and run bash). Pass it: `$PKG`, `$APK`, `$WORK`, the chosen **branch**,
the resolved `$RE` scripts dir, and the path to `re-digest-contract.md`. Its
instructions:

1. **Run RE per branch.**
   - **re-skill:** invoke the android-reverse-engineering skill on `$APK`,
     output dir `$WORK/output` — run its full workflow (fingerprint, deps,
     decompile, Kotlin-name recovery if Kotlin, API extraction incl. Tier-2).
   - **direct-scripts:** run, in order, reading each output before the next:
     `bash "$RE/fingerprint.sh" "$APK"`, `bash "$RE/check-deps.sh"`
     (install required deps via `bash "$RE/install-dep.sh" <dep>`; ask before
     optional vineflower/dex2jar), `bash "$RE/decompile.sh" -o "$WORK/output" "$APK"`
     (add `--deobf` if obfuscation is heavy), `bash "$RE/recover-kotlin-names.sh"
     "$WORK/output/sources" "$WORK/output/names/"` if Kotlin, then
     `bash "$RE/find-api-calls.sh" "$WORK/output/sources"`.
2. **Framework guard:** if the fingerprint is Flutter / React Native / Cordova
   / Xamarin, Java decompile is shallow — produce a partial digest, set
   `RE Method: limited: <framework>`, payloads may be empty.
3. **Extract** the Tier-1 endpoint inventory and Tier-2 payloads for **auth,
   payment/checkout, and the 1–2 core feature endpoints** (not every endpoint).
4. **Write** `$WORK/re-digest.md`, `$WORK/payloads.json`, `$WORK/re-summary.txt`
   exactly per `re-digest-contract.md`.
5. **Return** the contents of `$WORK/re-summary.txt` plus the two file paths —
   **never** raw decompiled sources.

If the subagent fails, retry once; if it still fails and the **direct-scripts**
branch is available (i.e. the Phase 2a probe returned `RC == 0`), re-dispatch on
that branch; otherwise stop and report.

### Phase 2c — Consume

Read `$WORK/re-summary.txt` (the only RE text in this context). From it you have:
framework, HTTP stack, host counts, endpoint count, key-flow names, secrets
count, and the RE method. Read `$WORK/re-digest.md` or `$WORK/payloads.json`
**on demand** when a later phase needs detail. Keep the summary in context for
Phases 3–7.

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
- read `$WORK/payloads.json`; the endpoint count and the payload complexity of
  the key flows size the backend work,
- the feature list + backend surface → AI-Sprint effort table (min-max total,
  uncertainty band; widen the band when RE Method is `limited:`),
- the MVP/Growth/Scale monthly infra cost table.
Base both on the **user-selected stack** from Phase 4.

## Phase 6: Market Viability Report

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/report-template.md`.
Fill every section from the data gathered. For market analysis (competitors,
market size), use web search as needed. Produce a GO / CONDITIONAL GO / NO GO
verdict tying effort + cost against market opportunity.
Include a **Backend API Surface** section: summarize the Tier-1 inventory from
`$WORK/re-digest.md` and the key-flow payloads from `$WORK/payloads.json` (host
list, endpoint count, auth model, and the auth/payment/core request+response
shapes). If RE Method was `limited:`, say so and note the reduced confidence.

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
| RE skill + scripts both missing | show resolver error, stop |
| RE subagent fails | retry once, then fall back to direct-scripts branch; else stop |
| Subagent returned no digest files | re-dispatch once; if still missing, stop and report |
| Flutter/RN/Cordova/Xamarin | warn, continue with limited RE |
| App Store not found | continue Google Play only |
| Play scrape returns nulls | web-search fallback, note source |
| Heavy obfuscation | add uncertainty band, note in report |
| writing-plans unavailable | write the plan as Markdown manually |
