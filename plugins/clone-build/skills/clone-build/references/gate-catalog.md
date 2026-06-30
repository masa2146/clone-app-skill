# Gate Catalog

Every task carries exactly one machine-checkable gate, run via `run-gate.sh`.
The gate `kind` is chosen by task type; the branch build guide supplies the
concrete `command`.

| Task type | Gate kind | Pass condition |
|---|---|---|
| logic / formula | **tdd** | failing test written first, then `<test cmd>` exits 0 |
| api / data model | **tdd** | contract test vs `payloads.json` shape exits 0 |
| ui (app) | **visual-diff** | `adb exec-out screencap` vs `screenshots/NN.png` matches ≥ threshold; **plus** build + launch no-crash |
| ui / scene (game) | **visual-diff** | `manage_camera(action="screenshot")` vs `screenshots/NN.png` matches |
| scaffold / design / any | **build** | compiles, 0 errors (`read_console` / gradle exit 0) |
| integration | **launch-crash** | app/scene starts, no fatal in logcat/console for N seconds |

`run-gate.sh --kind <kind> --command "<cmd>"` runs the command, prints an evidence
block, and propagates the exit code. `RESULT: PASS` iff exit 0. For `visual-diff`,
the command is the capture+compare step the branch guide provides; the model's match
verdict is recorded alongside the evidence.
