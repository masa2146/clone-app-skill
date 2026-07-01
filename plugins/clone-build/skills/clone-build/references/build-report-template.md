# Build Report — {APP_TITLE}

**Package:** {PACKAGE}  ·  **Date:** {DATE}  ·  **Branch:** {BRANCH} ({SUBSTACK})

## Summary
One paragraph: what was built, against which spec, the overall outcome.

## Tasks
Per task from `build-plan.json`: id, type, gate kind, final status (done /
needs-human-input), and the `RESULT: PASS` evidence line from `run-gate.sh`.

## Visual fidelity
Per screen: target `screenshots/NN.png` vs the built screenshot, match verdict.
For the app branch with no emulator, this section is marked **SKIP** with the reason
(visual-diff gates degrade to SKIP; the build/launch hard gate still ran).

## Gaps & assumptions
Anything from the plan's `gaps` list, plus `needs-human-input` tasks left for the user.

## Next manual steps
What remains outside this stage (publishing, store assets, etc.).
