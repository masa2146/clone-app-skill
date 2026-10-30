# Level Pipeline — measured lessons

For F10 (T070–T072) in any puzzle or physics clone that ships its own levels. Distilled
from a colour/queue/holding-slot puzzle (130+ own levels, 2200 source levels) and a physics
tower game (300 own levels). Numbers below were measured there; re-measure in your game.

**Order matters:** calibrate the measuring player → measure factor costs → build the
generator → gates and referees → regression sweep. Costs without a calibrated player, or a
generator without costs, produce numbers that mean nothing.

## 1. What the source game's difficulty label says (T070)

- Tabulate the source's difficulty label against level number and look for a rhythm first.
  In one game, past level 400 the label was a fixed rhythm by last digit (0 → very hard,
  5/9 → hard, 3/7 → medium, else easy; 80–98 % consistent). That is the designer's
  **intent**, not a measurement of the level.
- Take the rhythm as the **target** for your own levels. Never copy one level's label;
  measure your level.
- Static board counts (colours, depth, linked units, obstacle count) predict the label
  poorly (rank correlation 0.35–0.40, same band 34 %). An obstacle's mere presence adds
  ~0.06. Difficulty comes from position and timing → measure by simulation.

## 2. The measuring player

Keep two players; one cannot answer both questions.

| Player | Question | Use |
|---|---|---|
| **Solver** — deep search with backtracking | Do the rules allow finishing this level? | regression sweep |
| **Human-like** — greedy + slip probability, blind to hidden things | How hard is it for a person? | difficulty band |

- Costliest human-like bug: deciding only when the system is idle, one unit at a time, and
  scoring moves with a crude static heuristic ("how many lines show this colour"). It misses
  delayed costs (a linked unit with no ammo left keeps sitting in a holding slot) and rates
  easy levels "very hard" — it lost a quarter of the source's *easy* levels with zero slips.
  Patching the heuristic four times did not fix it.
- Short look-ahead (play each option 1–2 rounds in the head, pick by progress − held
  resource) helps a little (+10 % slip-free wins, label agreement unchanged).
- **Best: the learning player** (a rule, not ML). On a loss it inspects the jam at the end,
  blames one culprit (of the units left in holding slots, the earliest sent), remembers it,
  replays from the start and sends that unit last when another choice exists. At most 5
  tries. **Difficulty = the try it won on.** Measured: easy 1.6 · medium 2.9 · hard 3.9 ·
  very hard 4.2 tries, order never broken. It is what a player lives through and easy to
  read.
- **Second, independent measure: solver effort** (moves tried until solved). Easy ~130,
  medium ~210, hard ~1300, very hard mostly unsolved at 4000. As strong as the human-like
  player alone (0.49) but carries different information; together 0.54. Measure difficulty
  with at least two independent measures.
- **Calibrate on the source game's levels before your own:** a table of measured band ×
  source label, over a range where the label is not just the rhythm. If agreement is low,
  fix the player, not the levels.
- Guards every player needs:
  - give up when there is no progress (one level spun 30 minutes and locked the whole run;
    there: no cell cleared in 2 minutes of game time);
  - never tap while the wait/action queue is full — a rejected tap counted as "stuck"
    produced fake losses;
  - thinking copies (look-ahead clones) must not write to the trace or log.

## 3. The generator (T071): build to a plan, do not search for difficulty

Old way — random candidates → measure → keep the closest — is slow (~40 candidates per
level), drifts, and worst of all **ties variety and difficulty to one knob**: adding an
obstacle also adds difficulty, so easy levels stay obstacle-free, and feedback that fixes
one axis breaks the other (picture got nicer → obstacles left; more obstacles → picture
broke).

New way: **place difficulty as a plan with measured costs.**

1. **One common unit: resource pressure** (there: holding slots × time). A loss is running
   out of the resource; each factor's cost is "how many resources it holds, for how long",
   so costs add up.
2. **Costs from two sources:** regression on source data (says only "goes together"), and
   a **controlled ablation**: remove one factor from a level (link, hidden unit, ice, lock,
   blocker…), keep the rest, measure both; the difference is its cost. Put the same factor
   once in a cheap spot and once in an expensive one — **cost depends on position** (a gate
   on the outer edge ≈ 0; a triple link whose colours open at very different times holds
   3/5 of the slots for a long time). Drop levels where it is entangled with another
   mechanic.
3. **Separate variety from difficulty:** obstacles chosen for look and variety go in cheap
   spots first; then the difficulty budget is spent deliberately on expensive ones. Level
   130 can be easy and still not look like level 1.
4. **Block plan (10 levels):** difficulty rhythm; no two consecutive levels with the same
   obstacle combination; every unlocked type returns at least once per 10; a new mechanic
   appears 3 times in the next 10 with less help each time; at least half the block has 2
   types and at least 2 levels have 3; a deliberate breather level; the picture/theme is
   chosen so it can carry the obstacles' positions.
5. **Set-piece catalogue:** meaningful combinations of 2–3 mechanics ("the key that opens
   the lock comes out of the tunnel"), each with a measured cost; the same set-piece can be
   built cheap or expensive.
6. **Verify:** 3–5 candidates around the plan, the human-like player 16 games each; if it
   deviates, correct the budget by the cost in one step.

The first few levels are tutorials, handled separately; re-tune them once the system holds.

## 4. Gates and referees (T072)

The user is never the first to look at a level. Layers:

- **Automatic gates** (exact, measurable: band, invisible link, obstacle quota, rhythm). A
  candidate that fails a gate is never picked.
- **Level referee** — an independent subagent, one instruction file per level; material:
  opening frame, the source's frame, play trace, measurements. Last line
  `KARAR: GEÇTİ/KALDI — <reason>` (PASS/FAIL).
- **Sequence referee** — reviews 10 levels as one session played back to back: variety,
  rhythm, breathers, how each mechanic is taught.

Rules: at most 3 rounds, then ask the user; at most ~5 referee agents in parallel. Tell the
referee the measuring player's **known weakness**, or it takes the player's mistake for
design difficulty. When feedback asks to fix one axis, run the other axis's gate too (fixing
one and losing the other happened twice). Summarise reviews in one table (level, target,
round, verdict, measurement, one sentence on where the difficulty is); raw reviews stay in a
throwaway file.

## 5. Measurement infrastructure

- Parallel runs on APFS clones of the project (no extra disk), synced from the working tree
  before each run. On a 16 GB machine at most ~7 Unity instances at once.
- Timestamp result file names: an old result file with the same name was taken for "done"
  and the run was cut short.
- Pass list/folder paths as absolute paths (a relative path resolves elsewhere in a clone).
- Experiment switches via environment variables (version, penalty weight, retry count);
  before merge each one becomes permanent or is deleted, with a regression test.
- Any change to rules, mechanics or the player → full regression sweep with the solver over
  every level (scarce resource, plenty of resource, save-and-resume). No merge while any
  level is lost.
- Every claim measured. Three things written as "probably" (palette order, cost, footprint)
  were silently wrong.
