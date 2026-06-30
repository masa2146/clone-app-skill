# Build-Plan Contract

`gen-build-plan.py` emits `build-plan.json`. This is the contract every executor
and reviewer relies on. Generation is **deterministic** — no clock, no randomness;
the same spec + artifacts produce byte-identical output.

## Top-level shape
```json
{
  "package": "com.example.app",
  "title": "Example App",
  "branch": "app | game",
  "substack": "unity | flutter | react-native | native-android | unknown",
  "generated_from": "<absolute path to clone-build-spec.md>",
  "gaps": [ { "artifact": "payloads.json", "reason": "missing" } ],
  "tasks": [ /* see below */ ]
}
```

## Task shape
```json
{
  "id": "screen-login",
  "type": "scaffold | design | ui | scene | logic | api | integration",
  "title": "Build app screen: Login",
  "inputs": ["<absolute artifact paths>"],
  "instructions": "<concrete, unambiguous steps>",
  "gate": { "kind": "build|tdd|visual-diff|launch-crash", "command": "", "pass_when": "<text>" },
  "status": "pending | needs-human-input | done",
  "depends_on": ["scaffold", "design-system"]
}
```

In the skeleton, `gate.command` is empty — the branch build guide (app or game)
fills it with the concrete command before execution. `gate.kind` and
`gate.pass_when` are final.

## Task generation rules (deterministic)
- `scaffold` (build gate) → `design-system` (build gate) come first.
- One screen task per `nav-graph.json` node, sorted by node id. `ui` for app,
  `scene` for game. Gate `visual-diff`.
- One `api` task per `payloads.json` endpoint, sorted by (host, path, method).
  Gate `tdd`.
- One `logic` task per `logic-signals.json` signal (optional artifact), sorted by
  name. Gate `tdd`.
- `integration` task last; `depends_on` all screen + api tasks. Gate `launch-crash`.

## Spec-completeness / gaps
Required artifacts: `design-tokens.json`, `payloads.json`, `nav-graph.json`, and at
least one `screenshots/*.png`. Each missing or empty one becomes a `gaps` entry, and
every task that depends on it is emitted with status `needs-human-input` instead of
`pending` — the build never silently generates code on a hole.

## The forcing rule
A task may not be marked `done` until its gate command has been run through
`run-gate.sh` and `RESULT: PASS` (exit 0) was produced. The gate evidence block is
pasted into the task report. The reviewer re-checks that evidence before any
dependent task is unblocked. No evidence → the task stays open. This is what keeps a
weak model on rails: the model never self-certifies "looks done"; a command exits 0
or it does not.
