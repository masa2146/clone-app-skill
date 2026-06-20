# Clone App Skill — Design Spec

**Date:** 2026-06-21  
**Status:** Approved  
**Repo:** fork of `masa2146/android-reverse-engineering-skill`

---

## Overview

A Claude Code skill (`/clone-app`) that takes a Google Play URL, downloads the APK, reverse engineers it, analyzes the app store presence, estimates clone effort with AI-assisted tooling, evaluates market viability, and optionally generates a full implementation plan.

**Trigger:**
```
/clone-app https://play.google.com/store/apps/details?id=com.example.app
```

---

## Repository Structure

The skill lives inside the fork of `android-reverse-engineering-skill` as a separate plugin — upstream files are never modified.

```
masa2146/android-reverse-engineering-skill/
├── plugins/
│   ├── android-reverse-engineering/        ← upstream, untouched
│   │   └── skills/android-reverse-engineering/
│   │       ├── SKILL.md
│   │       └── scripts/                    ← called directly by clone-app
│   └── clone-app/                          ← new skill
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── skills/
│       │   └── clone-app/
│       │       └── SKILL.md
│       └── commands/
│           └── clone-app.md
```

**Upstream sync:**
```bash
git remote add upstream https://github.com/SimoneAvogadro/android-reverse-engineering-skill.git
git pull upstream master
```
Conflict risk is low — upstream only modifies `plugins/android-reverse-engineering/` and root files (README, LICENSE).

---

## Architecture

### Approach: Orchestrator Skill (Option B)

`clone-app` SKILL.md orchestrates all phases sequentially. RE bash scripts are called directly via relative path from within the same repo — no cross-plugin tool invocation needed.

RE script path pattern:
```bash
RE_SCRIPTS="$(dirname "$CLAUDE_PLUGIN_ROOT")/../android-reverse-engineering/skills/android-reverse-engineering/scripts"
bash "$RE_SCRIPTS/fingerprint.sh" app.xapk
bash "$RE_SCRIPTS/decompile.sh" app.xapk
bash "$RE_SCRIPTS/find-api-calls.sh" output/sources/
```

---

## Phase Workflow

### Phase 0: Input Validation
- Extract package name from URL via regex: `id=([a-zA-Z0-9._]+)`
- If extraction fails → ask user to provide package name directly
- Create working directory: `./work/{package}/`

### Phase 1: APK Download
```bash
curl -L "https://d.apkpure.com/b/APK/{PACKAGE}?version=latest" --output work/{package}/app.xapk
```
- 3 retries on failure
- Detect file type (APK vs XAPK) from magic bytes
- If download fails after retries → ask user for local APK path

### Phase 2: Reverse Engineering
Calls RE skill scripts in order:

1. `fingerprint.sh` — framework detection (Flutter/RN/Kotlin/etc.), HTTP stack, obfuscation level
2. `check-deps.sh` — verify jadx, Java 17+ present; auto-install if missing via `install-dep.sh`
3. `decompile.sh` — full decompile to `work/{package}/output/sources/`
4. `recover-kotlin-names.sh` — R8 deobfuscation (if Kotlin app)
5. `find-api-calls.sh` — extract all API endpoints (Retrofit, OkHttp, Ktor, Apollo, etc.)

**Output:** tech stack JSON, API endpoint list, AndroidManifest summary, detected features.

**Flutter/RN/Cordova fallback:** fingerprint detects framework → warn user "Java decompile limited for this framework" → proceed with what's available (manifest, hardcoded URLs, SDK list).

### Phase 3: Store Analysis
- Scrape Google Play store page for: rating, review count, install range, category, last update, developer
- Search App Store for same package → note if iOS version exists
- If App Store not found → continue with Google Play data only

**Output:** store metrics JSON.

### Phase 4: Stack Recommendation
AI analyzes RE results + store data and proposes 2-3 clone stack options:
- Considers detected original stack
- Considers AI-assisted development efficiency (Flutter and React Native favored for speed)
- Presents tradeoffs for each option

Present to user:
> "Detected: Native Kotlin. Recommended for AI-assisted clone: Flutter (fastest) or React Native (JS ecosystem). Original stack also viable. Which do you prefer?"

User selects stack → locked for Phase 5+.

### Phase 5: Effort & Cost Estimation
Based on selected stack:

**Feature list** extracted from APK:
- Screens (Activity/Fragment count)
- Permissions used
- API endpoints count
- Third-party SDKs (payment, auth, analytics, etc.)
- Detected backend patterns (REST/GraphQL/WebSocket)

**AI-assisted effort table:**

| Category | Complexity | AI Sprints |
|----------|-----------|------------|
| Auth flow | Medium | 1 |
| Core screens | High | 3-5 |
| API integration | Medium | 2 |
| Backend (if needed) | High | 3-8 |
| ... | ... | ... |

"AI Sprint" = one focused Claude Code session (~2-4 hours of human review time).

**Infrastructure cost estimate:**
- Backend hosting (Railway/Render/AWS estimate)
- Database
- CDN / storage
- Third-party API costs (maps, payments, etc.)

### Phase 6: Market Viability Report

Synthesizes all data into `work/{package}/clone-report-YYYY-MM-DD.md`:

```markdown
## App Overview
## Tech Stack (Detected)
## Recommended Clone Stack
## Feature List (from APK)
## Effort Estimate (AI-assisted)
## Infrastructure Cost Estimate (monthly)
## Market Analysis
  - Current app metrics
  - Competitor landscape
  - Target market size estimate
## Viability Verdict
  - GO / CONDITIONAL GO / NO GO
  - Key risks
  - Key opportunities
```

### Phase 7: Decision Gate
Present report summary to user:

> "Report saved to work/{package}/clone-report-YYYY-MM-DD.md. Want to proceed with building the implementation plan?"

- **Yes** → invoke `writing-plans` skill with report as context
- **No** → save report, end skill

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| APKPure download fails (3x) | Ask user for local APK path |
| XAPK (split bundle) | RE skill handles automatically |
| Flutter/RN/Cordova app | Warn, continue with available data |
| App Store not found | Continue with Google Play only |
| RE skill not installed | Run `check-deps.sh`, auto-install missing tools |
| Package name not in URL | Ask user to input package name |
| `writing-plans` skill unavailable | Write plan as Markdown manually |
| Heavy obfuscation | Note in report, feature list may be incomplete |

---

## Known Limitations

- iOS API extraction not possible (store scrape only, no IPA download)
- Effort estimates are AI-sprint based, not calendar time — depends on developer review speed
- Play Store download counts are ranges (not exact) — viability estimate uses midpoint
- APKPure availability not guaranteed for all apps
- Heavy R8 obfuscation may limit feature detection accuracy

---

## Working Directory Layout

```
./work/{package}/
├── app.xapk                     ← downloaded APK
├── output/
│   ├── sources/                 ← decompiled Java/Kotlin
│   └── names/                   ← Kotlin name recovery maps
├── clone-report-YYYY-MM-DD.md  ← final report
└── implementation-plan.md      ← generated by writing-plans
```

---

## Dependencies

**Skill dependencies:**
- `android-reverse-engineering` plugin (same repo)
- Java JDK 17+
- jadx (auto-installed if missing)
- curl

**Optional:**
- Vineflower/Fernflower (better decompile quality)
- dex2jar

---

## Installation

```bash
# 1. Clone fork
git clone https://github.com/masa2146/android-reverse-engineering-skill.git
cd android-reverse-engineering-skill

# 2. Install both plugins
/plugin marketplace add .
/plugin install android-reverse-engineering@android-reverse-engineering-skill
/plugin install clone-app@android-reverse-engineering-skill
```

---

## Out of Scope

- Automated code generation of the clone (that's writing-plans → executing-plans)
- iOS IPA download/reverse engineering
- Real-time market data (uses scraped/estimated data)
- Legal review of clone viability
