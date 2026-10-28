---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
description: Run the project's task loop — next task, its detail file, gates, dated delivery, merge on approval
user-invocable: true
argument-hint: sonraki | durum | bitir <ID> | ekle "<iş>" --faz "<F..>"
argument: subcommand (default sonraki)
---

# /task

One task per session, from `Docs/TASKS.md` (laid out by `/clone-build kur`).
Scripts: `T=${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts`. Run them from the
project root. If `Docs/TASKS.md` is missing, tell the user to run `/clone-build kur`.

## sonraki (default)

1. `python3 $T/tasks.py next` — it marks the task `sürüyor`, writes
   `Docs/tasks/<ID>-<ad>.md` and switches to the task's branch. If a task is already
   running it names that one: continue it instead.
2. Fill the detail file before touching code: Özet (what and why, the "bitti sayılır"
   line restated as checks), Plan in superpowers **writing-plans** format (use the
   skill when installed; otherwise the same headings by hand), Teknik.
3. List every permission the task will need (Unity runs, device, browser, server,
   pushes) and ask the user **once**, in one message. No questions mid-task.
4. Work the plan on the branch. A new piece of work found on the way goes to
   `tasks.py add`, not into this task.
5. Run the gate named in the task's Kapı column and write each command + its result
   under "Kontroller". Gate tools: tests; clone-app `check-extraction.py` (G1);
   `VerifyImport` / `ImportUI` VerifyBatch against `expected-import.py` /
   `expected-ui.py` (G1, G9); `/qa` for any web page or UI flow; the level referee
   (G8); a comparison clip, ours left, reference right, same level same moment (G9).
   "Passed" only with the output in hand.
6. `python3 $T/teslim.py <ID> <kısa-ad> <files…> --not "<one line>"` — copies the
   evidence to the dated delivery folder and marks the task `teslimde`.
7. Report to the user: result first, the delivery paths exactly as teslim.py printed
   them (full paths, code block, one per line), then ask **"birleştireyim mi?"**.

## bitir <ID>

Only after the user said yes: `git switch main && git merge --no-ff <branch>`, run
the tests once more on main, then `python3 $T/tasks.py set <ID> bitti`. Never push.

## durum

`python3 $T/tasks.py list --open` and the "Şu an" block of `Docs/TASKS.md`; report
running, waiting-for-approval and next in three lines.

## ekle "<iş>" --faz "<F..>"

`python3 $T/tasks.py add "<iş>" --faz "<faz>" [--kapi G9] [--bitti "<…>"]`.
