---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
description: Prepare a game's Play store listing — research, texts in many languages, three image styles, trailer, checks, review page
user-invocable: true
argument-hint: [rakip | metin | gorsel | fragman | sayfa | yukle]
argument: step to run (optional; default runs the whole flow)
---

# /magaza

Follow `${CLAUDE_PLUGIN_ROOT}/skills/magaza/SKILL.md`. With no argument run steps 1–6 and stop
at the review page with one question: which style goes to the default listing. A step name runs
only that step. `yukle` (step 7) runs only after the user chose a style. Never upload past a
`denetle.py` HATA.
