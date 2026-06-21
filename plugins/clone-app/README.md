# clone-app — Clone Feasibility Analyzer (Claude Code skill)

Give it a Google Play URL. It downloads the APK, reverse engineers the tech
stack and APIs (via the sibling `android-reverse-engineering` plugin), analyzes
the app's store presence, estimates **AI-assisted** build effort (in AI Sprints)
and monthly infrastructure cost, judges market viability (GO / CONDITIONAL GO /
NO GO), and — if you approve — generates a full implementation plan.

## Requirements
- The `android-reverse-engineering` plugin (ships in this same repo).
- Java JDK 17+ and jadx (the RE plugin auto-installs jadx if missing).
- `curl`, Python 3 (stdlib only), `unzip`.
- **bash 4+**. macOS ships bash 3.2, but the RE scripts use bash-4 syntax
  (`${VAR,,}`) and fail with "bad substitution" on 3.2. Install a modern bash
  with `brew install bash` — `#!/usr/bin/env bash` then picks it up.

## APK source
APKs/XAPKs are fetched from **APKCombo**. The previous APKPure direct endpoint
(`d.apkpure.com/b/APK/<pkg>`) now returns an HTTP 403 Cloudflare bot challenge
for every package, so it is no longer usable from a plain `curl`. If an app is
not on APKCombo, pass a local `.apk`/`.xapk` path instead.

## Install
```text
/plugin marketplace add https://github.com/masa2146/clone-app-skill
/plugin install android-reverse-engineering@clone-app-skill
/plugin install clone-app@clone-app-skill
```

## Usage
```text
/clone-app https://play.google.com/store/apps/details?id=com.example.app
```
Or natural language: "Analyze this Play Store app for cloning: <url>".

The skill pauses twice for your input: choosing the clone stack, and deciding
whether to generate the implementation plan.

## Output
```
./work/<package>/
├── app.apk | app.xapk
├── output/            # decompiled sources + Kotlin name maps
├── play.json          # store metrics
├── appstore.json      # iOS presence
└── clone-report-YYYY-MM-DD.md
```

## Keeping the RE plugin up to date
This repo is a fork. To pull upstream improvements:
```bash
git remote add upstream https://github.com/SimoneAvogadro/android-reverse-engineering-skill.git
git pull upstream master
```
The clone-app plugin lives in its own directory, so upstream updates to
`android-reverse-engineering` merge cleanly.

## Legal
For lawful use only — your own apps, authorized interoperability, security
research, or education. You are responsible for compliance.
