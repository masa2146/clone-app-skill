---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
description: Run the project's task loop — next task, its detail file, gates, dated delivery, merge on approval
user-invocable: true
argument-hint: sonraki [--worktree] | durum | bitir <ID> | ekle "<iş>" --faz "<F..>"
argument: subcommand (default sonraki)
---

# /task

One task per session, from `Docs/TASKS.md` (laid out by `/clone-build kur`).
Scripts: `T=${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts`. Run them from the
project root. If `Docs/TASKS.md` is missing, tell the user to run `/clone-build kur`.

## sonraki (default)

1. `python3 $T/tasks.py next` — it marks the task `sürüyor`, writes
   `Docs/tasks/<ID>-<ad>.md` and switches to the task's branch. If a task is already
   running it names that one: continue it instead. **If another session is working in
   this project** (check the agent list / the status doc's parallel table), use
   `tasks.py next --worktree`: the task gets its own folder `../<repo>-<branch>`; write
   code there. The task book stays in the main checkout — tasks.py and teslim.py find it
   from either folder, so a task branch never edits `Docs/TASKS.md`. Once a project uses worktrees,
   the main checkout stays on main (tasks.py warns otherwise); `temizle` deletes only
   worktrees whose task the book marks `bitti` and whose branch is merged.
2. Fill the detail file before touching code: Özet (what and why, the "bitti sayılır"
   line restated as checks), Plan in superpowers **writing-plans** format (use the
   skill when installed; otherwise the same headings by hand), Teknik.
3. List every permission the task will need (Unity runs, device, browser, server,
   pushes) and ask the user **once**, in one message. No questions mid-task except the
   visual picks below.
4. Work the plan on the branch. A new piece of work found on the way goes to
   `tasks.py add`, not into this task. Independent parts of the plan go to fresh
   subagents (superpowers **subagent-driven-development**); the main session keeps the
   user conversation and reviews each part's evidence.
   **If the task changes what the player sees**, read
   `${CLAUDE_PLUGIN_ROOT}/skills/clone-build/references/art-pipeline.md` first and follow
   its gates: options drawn in the game frame (`scripts/art/ctx.py`), a board
   (`scripts/art/pano.py`) sent with full paths, then `AskUserQuestion` (≤ 3 options,
   recommendation first, what the player will see, the source's own level as one option)
   **before** building a model and again before delivery. Record the pick in KARARLAR.
   Never approve a look yourself, and never fall back to code-drawn or primitive art for
   a class the asset-class table gives to Gemini or image-to-3D.
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

Only after the user said yes. First `python3 $T/tasks.py bayat`: if this task is
BAYAT, the code changed after the evidence was made; re-run the gate, deliver
again with teslim.py and ask again instead of merging. Then, in
the main checkout: `git status` — files the build regenerates every time (listed in
KARARLAR) are restored; anything else dirty stops the merge and goes to the user.
`git switch main && git merge --no-ff <branch>`, run the tests once more on main,
`python3 $T/tasks.py set <ID> bitti`, commit `Docs/TASKS.md` and `Docs/tasks/` on main,
then `python3 $T/tasks.py temizle --yes` (removes the merged worktree; one with unsaved
work is kept and named). If another session works in this project, tell it about the
merge before anyone pushes. Never push unless the user asks.

## durum

`python3 $T/tasks.py list --open`, `python3 $T/tasks.py bayat`, `python3 $T/tasks.py disk`
and the "Şu an" block of `Docs/TASKS.md`; report running, waiting-for-approval (with
"kanıt bayat" where bayat says so) and next in three lines, plus one line when the disk
is under its threshold.

When a task's phase starts, read that phase's section of
`${CLAUDE_PLUGIN_ROOT}/skills/clone-build/references/lessons.md` — the traps two shipped
clones paid days for.

## ekle "<iş>" --faz "<F..>"

`python3 $T/tasks.py add "<iş>" --faz "<faz>" [--kapi G9] [--bitti "<…>"]`.
