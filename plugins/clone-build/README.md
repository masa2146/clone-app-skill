# clone-build

The build/verify stage of the **discover → analyze → build** pipeline
(`market-research → clone-app → clone-build`). Takes the `clone-build-spec.md` and
`$WORK/` artifacts produced by clone-app (Phase 9) and drives them to running,
verified, production-ready code.

## How it works

A shared 6-phase spine (`skills/clone-build/SKILL.md`) plus two on-demand branch
guides:

- **app** branch — Flutter / native Android / React Native. Build + install + launch
  hard gate always; `adb screencap` visual-diff when an emulator is present.
- **game** branch — Unity, driven live via the MCP-for-Unity tools (scaffold via
  Unity CLI, build/screenshot/test gates).

Robustness is structural: `gen-build-plan.py` emits a deterministic task graph where
every task carries a machine-checkable gate (`build` / `tdd` / `visual-diff` /
`launch-crash`), run through `run-gate.sh`. A task is `done` only when its gate
exits 0 — the model never self-certifies. Execution uses
`superpowers:subagent-driven-development` (fresh subagent + reviewer per task).

## Scripts
- `detect-branch.sh` — spec → `game|app` + substack.
- `preflight.sh` — probe Unity / flutter / gradle / node / adb, free disk and transcript retention → JSON.
- `gen-build-plan.py` — spec + artifacts → `build-plan.json` (deterministic).
- `run-gate.sh` — single gate-execution chokepoint.
- `scaffold-project.py` — `/clone-build kur`: day-one layout (CLAUDE.md, `Docs/TASKS.md`
  from `templates/lifecycle.tsv`, `.gitignore`, delivery folder, clone-app's Unity kit).
- `tasks.py` — `/task`: next task, its detail file and branch (`--worktree`: its own folder for
  parallel sessions); status, add, list; `bayat` (stale evidence); `temizle` (remove merged
  worktrees, measured with df); `disk` (free-space threshold).

## References
- `references/lessons.md` — traps two shipped clones paid days for, by phase, linked from the
  lifecycle rows: store clocks, disk budget, faithful-copy freeze, phone-only bugs, purchases,
  remote updates, Unity build traps, store review.
- `references/art-pipeline.md` — the visual production line: user-picked style board and object
  batches, asset-class → tool table, Gemini, in-frame rehearsal, image-to-3D, toon rules,
  performance budget. Tools in `scripts/art/` (`gem.sh`, `fit.py`, `ctx.py`, `pano.py`, `tripo_prep.py`).
- `teslim.py` — copy a task's evidence to `<teslim-root>/<game>/teslim/<date>/` and print full paths.

## Skills
- `clone-build` — the spine above. `/task` — the per-session task loop.
- `temizlik` — sweep the leftovers agent sessions leave (merged worktrees and their Library copies,
  merged branches, old logs, superseded builds, stale scratchpads); lists first, deletes on "evet".

## Tests
```bash
bash plugins/clone-build/tests/run-all.sh
```
Offline fixtures only — no live Unity / emulator / network.

## Status
Branch-agnostic core. The app branch, game branch, and clone-app Phase-7 wiring land
in later plans.
