---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, WebFetch, WebSearch, Skill
description: Analyze a Google Play app for cloning — RE, effort, market viability, optional plan
user-invocable: true
argument-hint: <Google Play URL or package name>
argument: Google Play URL or package name (optional)
---

# /clone-app

Run the full clone-feasibility workflow on a Google Play app.

## Instructions

Follow the clone-app skill workflow in
`${CLAUDE_PLUGIN_ROOT}/skills/clone-app/SKILL.md` exactly, phases 0 through 7.

### Step 1: Get the target
If the user passed a URL or package name as an argument, use it. Otherwise ask
for the Google Play URL or package name.

### Step 2: Run the skill
Execute Phase 0 → Phase 7 from SKILL.md. Pause for the user at:
- Phase 4 (stack choice),
- Phase 7 (proceed to implementation plan?).

Honor the Error Handling Summary table in SKILL.md at every phase.

### Step 3: Deliver
Ensure the report is written to `./work/<package>/clone-report-<date>.md` and
summarize the verdict. If the user approves at Phase 7, invoke
`superpowers:writing-plans` with the report as the spec.
