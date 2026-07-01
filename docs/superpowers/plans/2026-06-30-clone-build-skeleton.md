# clone-build Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the branch-agnostic core of the `clone-build` plugin — the fourth pipeline stage that turns a `clone-build-spec.md` + `$WORK/` artifacts into a deterministic task graph (`build-plan.json`) with machine-checkable gates, plus the SKILL.md spine, contracts, scripts, and tests.

**Architecture:** A new plugin `plugins/clone-build/` mirroring the existing plugin layout. The SKILL.md holds the shared 6-phase spine (P0–P5); game/app specifics live in reference files loaded on demand (later plans). The core is four scripts (`detect-branch.sh`, `preflight.sh`, `run-gate.sh`, `gen-build-plan.py`) and three references (`plan-contract.md`, `gate-catalog.md`, `build-report-template.md`). `gen-build-plan.py` is deterministic (no clock/random) and reads structured artifacts, so the plan is fixture-testable offline.

**Tech Stack:** bash 4+ (`#!/usr/bin/env bash`, run via `bash <path>`), Python 3 stdlib-only (`json`, `re`, `os`, `argparse` — no pip, no virtualenv). Tests use `set -uo pipefail`, aggregate failures, exit non-zero on any fail; offline fixtures only.

## Global Constraints

- **Upstream untouched:** `git status --porcelain plugins/android-reverse-engineering/` MUST print nothing. Never create or modify any file under that tree.
- **Working dir convention:** runtime artifacts go to `./work/<pkg>/` relative to the user's cwd — never inside any plugin. (Plans/tests use `tests/fixtures/` only.)
- **Scripts:** `#!/usr/bin/env bash`; invoke with `bash <path>`. Python is **stdlib-only**.
- **Determinism:** `gen-build-plan.py` takes no clock and no randomness — same inputs produce byte-identical output.
- **Branch-agnostic only:** this plan builds the core. The app branch, game branch, and clone-app Phase-7 wiring are separate later plans. Gate `command` fields are left empty here (filled by branch guides later); only gate `kind` and `pass_when` are populated.
- **Commits:** Conventional Commits scoped to the plugin — `feat(clone-build): …`, `test(clone-build): …`.
- **Branch + gate vocabulary (use these exact tokens everywhere):**
  - branch ∈ `game | app`; substack ∈ `unity | flutter | react-native | native-android | unknown`
  - task type ∈ `scaffold | design | ui | scene | logic | api | integration`
  - gate kind ∈ `build | tdd | visual-diff | launch-crash`
  - task status ∈ `pending | needs-human-input | done`

---

### Task 1: `detect-branch.sh` — classify a spec as game|app + substack

**Files:**
- Create: `plugins/clone-build/skills/clone-build/scripts/detect-branch.sh`
- Create: `plugins/clone-build/tests/fixtures/spec-app.md`
- Create: `plugins/clone-build/tests/fixtures/spec-game.md`
- Test: `plugins/clone-build/tests/test-detect-branch.sh`

**Interfaces:**
- Consumes: a `clone-build-spec.md` path (arg 1).
- Produces: prints `<branch> <substack>` to stdout (e.g. `app flutter`, `game unity`); exit 0 on success, 2 on usage/missing-file, 3 if no `Selected stack` line. Detection reads **only** the `Selected stack` line (not the whole file — the spec template always carries a "Game variant (Unity)" section, so whole-file scanning would false-positive).

- [ ] **Step 1: Create the two spec fixtures**

`plugins/clone-build/tests/fixtures/spec-app.md`:
```markdown
# Clone Build Spec — Acme Notes

**Package:** com.acme.notes  ·  **Date:** 2026-06-30  ·  **Selected stack:** Flutter + Firebase + Riverpod

## 1. Product overview
A notes app.

## Game variant (Unity)
(unused for this app — template boilerplate that must NOT trigger game detection)
```

`plugins/clone-build/tests/fixtures/spec-game.md`:
```markdown
# Clone Build Spec — Blast Saga

**Package:** com.blast.saga  ·  **Date:** 2026-06-30  ·  **Selected stack:** Unity 2022 LTS (IL2CPP) + Photon

## 1. Product overview
A match-3 game.
```

- [ ] **Step 2: Write the failing test**

`plugins/clone-build/tests/test-detect-branch.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-build/scripts/detect-branch.sh"
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}

check "app+flutter" "app flutter"  "$(bash "$SCRIPT" "$HERE/fixtures/spec-app.md")"
check "game+unity"  "game unity"    "$(bash "$SCRIPT" "$HERE/fixtures/spec-game.md")"

bash "$SCRIPT" >/dev/null 2>&1; check "usage exit 2" "2" "$?"
bash "$SCRIPT" "$HERE/fixtures/does-not-exist.md" >/dev/null 2>&1; check "missing exit 2" "2" "$?"

exit $fail
```

- [ ] **Step 3: Run test to verify it fails**

Run: `bash plugins/clone-build/tests/test-detect-branch.sh`
Expected: FAIL (script does not exist yet).

- [ ] **Step 4: Write the script**

`plugins/clone-build/skills/clone-build/scripts/detect-branch.sh`:
```bash
#!/usr/bin/env bash
# Classify a clone-build-spec.md as game|app + substack from its "Selected stack" line.
# Reads ONLY that line — the spec template always carries a "Game variant (Unity)"
# section, so whole-file scanning would false-positive every app as a game.
set -uo pipefail

SPEC="${1:-}"
if [[ -z "$SPEC" || ! -f "$SPEC" ]]; then
  echo "ERROR: usage: detect-branch.sh <clone-build-spec.md>" >&2
  exit 2
fi

line="$(grep -i 'selected stack' "$SPEC" | head -n1 | tr 'A-Z' 'a-z')"
if [[ -z "$line" ]]; then
  echo "ERROR: no 'Selected stack' line in $SPEC" >&2
  exit 3
fi

branch=app; substack=unknown
case "$line" in
  *unity*|*il2cpp*)            branch=game; substack=unity ;;
  *flutter*)                   substack=flutter ;;
  *react*native*)              substack=react-native ;;
  *native*|*kotlin*|*compose*|*jetpack*) substack=native-android ;;
esac

echo "$branch $substack"
```

- [ ] **Step 5: Make executable and run test to verify it passes**

Run:
```bash
chmod +x plugins/clone-build/skills/clone-build/scripts/detect-branch.sh
bash plugins/clone-build/tests/test-detect-branch.sh
```
Expected: all PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-build/skills/clone-build/scripts/detect-branch.sh \
        plugins/clone-build/tests/test-detect-branch.sh \
        plugins/clone-build/tests/fixtures/spec-app.md \
        plugins/clone-build/tests/fixtures/spec-game.md
git commit -m "feat(clone-build): add detect-branch.sh + fixtures"
```

---

### Task 2: `preflight.sh` — probe build toolchains → JSON

**Files:**
- Create: `plugins/clone-build/skills/clone-build/scripts/preflight.sh`
- Test: `plugins/clone-build/tests/test-preflight.sh`

**Interfaces:**
- Consumes: optional `--out <path>` (write JSON to file instead of stdout).
- Produces: a JSON object with boolean keys `unity, flutter, gradle, node, adb, adb_device, python3`. `adb_device` is true only if `adb devices` lists a device in `device` state. Exit 0.

- [ ] **Step 1: Write the failing test**

`plugins/clone-build/tests/test-preflight.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-build/scripts/preflight.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fail=0
check() { local d="$1" c="$2"; if [[ "$c" == "1" ]]; then echo "PASS: $d"; else echo "FAIL: $d"; fail=1; fi; }

# Mock a PATH where `flutter` exists but `gradle` does not.
mkdir -p "$TMP/bin"
printf '#!/usr/bin/env bash\nexit 0\n' > "$TMP/bin/flutter"; chmod +x "$TMP/bin/flutter"
out="$(PATH="$TMP/bin:/usr/bin:/bin" bash "$SCRIPT")"
echo "$out"
python3 - "$out" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
assert d["flutter"] is True, "flutter should be true"
assert d["gradle"] is False, "gradle should be false"
for k in ["unity","flutter","gradle","node","adb","adb_device","python3"]:
    assert k in d, f"missing key {k}"
print("ok")
PY
check "valid JSON with expected keys/values" "$([[ $? -eq 0 ]] && echo 1)"

# --out writes a file
PATH="$TMP/bin:/usr/bin:/bin" bash "$SCRIPT" --out "$TMP/pf.json" >/dev/null
[[ -s "$TMP/pf.json" ]] && check "--out wrote file" 1 || check "--out wrote file" 0

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-build/tests/test-preflight.sh`
Expected: FAIL (script missing).

- [ ] **Step 3: Write the script**

`plugins/clone-build/skills/clone-build/scripts/preflight.sh`:
```bash
#!/usr/bin/env bash
# Probe build toolchains → JSON capability map on stdout (or --out <file>).
# Branch-agnostic: branch guides read the relevant keys. Never fails the pipeline.
set -uo pipefail

OUT=""
if [[ "${1:-}" == "--out" ]]; then OUT="${2:-}"; fi

have() { command -v "$1" >/dev/null 2>&1 && echo true || echo false; }

adb_device=false
if command -v adb >/dev/null 2>&1; then
  if adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{f=1} END{exit f?0:1}'; then
    adb_device=true
  fi
fi

json="$(cat <<JSON
{
  "unity": $(have unity),
  "flutter": $(have flutter),
  "gradle": $(have gradle),
  "node": $(have node),
  "adb": $(have adb),
  "adb_device": $adb_device,
  "python3": $(have python3)
}
JSON
)"

if [[ -n "$OUT" ]]; then
  printf '%s\n' "$json" > "$OUT"
  echo "wrote $OUT"
else
  printf '%s\n' "$json"
fi
```

- [ ] **Step 4: Make executable and run test to verify it passes**

Run:
```bash
chmod +x plugins/clone-build/skills/clone-build/scripts/preflight.sh
bash plugins/clone-build/tests/test-preflight.sh
```
Expected: all PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-build/skills/clone-build/scripts/preflight.sh \
        plugins/clone-build/tests/test-preflight.sh
git commit -m "feat(clone-build): add preflight.sh toolchain probe"
```

---

### Task 3: `run-gate.sh` — single gate-execution chokepoint

**Files:**
- Create: `plugins/clone-build/skills/clone-build/scripts/run-gate.sh`
- Test: `plugins/clone-build/tests/test-run-gate.sh`

**Interfaces:**
- Consumes: `--kind <build|tdd|visual-diff|launch-crash> --command "<shell command>"`.
- Produces: prints an evidence block (`GATE kind=…`, `COMMAND:`, `EXIT:`, `---evidence---` … `---end---`, `RESULT: PASS|FAIL`) and **propagates the command's exit code**. `RESULT: PASS` iff the command exited 0. Bad/missing args exit 2. This is the one chokepoint both the executor subagent and the reviewer call to verify a task's gate.

- [ ] **Step 1: Write the failing test**

`plugins/clone-build/tests/test-run-gate.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-build/scripts/run-gate.sh"
fail=0
check() { local d="$1" e="$2" a="$3"; if [[ "$e" == "$a" ]]; then echo "PASS: $d"; else echo "FAIL: $d — expected '$e' got '$a'"; fail=1; fi; }

out="$(bash "$SCRIPT" --kind build --command true)"; rc=$?
check "pass exit 0" "0" "$rc"
echo "$out" | grep -q "RESULT: PASS" && check "pass result line" 1 1 || check "pass result line" 1 0

out="$(bash "$SCRIPT" --kind tdd --command false)"; rc=$?
check "fail exit 1" "1" "$rc"
echo "$out" | grep -q "RESULT: FAIL" && check "fail result line" 1 1 || check "fail result line" 1 0

echo "$out" | grep -q -- "---evidence---" && check "evidence block" 1 1 || check "evidence block" 1 0

bash "$SCRIPT" --kind bogus --command true >/dev/null 2>&1; check "bad kind exit 2" "2" "$?"
bash "$SCRIPT" --kind build >/dev/null 2>&1; check "missing command exit 2" "2" "$?"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-build/tests/test-run-gate.sh`
Expected: FAIL (script missing).

- [ ] **Step 3: Write the script**

`plugins/clone-build/skills/clone-build/scripts/run-gate.sh`:
```bash
#!/usr/bin/env bash
# Single chokepoint: run one gate command, emit an evidence block, propagate exit.
# Usage: run-gate.sh --kind <build|tdd|visual-diff|launch-crash> --command "<cmd>"
set -uo pipefail

kind=""; command_str=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kind)    kind="${2:-}"; shift 2 ;;
    --command) command_str="${2:-}"; shift 2 ;;
    *) echo "ERROR: unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$kind" in
  build|tdd|visual-diff|launch-crash) ;;
  *) echo "ERROR: --kind must be build|tdd|visual-diff|launch-crash" >&2; exit 2 ;;
esac
if [[ -z "$command_str" ]]; then echo "ERROR: --command required" >&2; exit 2; fi

echo "GATE kind=$kind"
echo "COMMAND: $command_str"
out="$(bash -c "$command_str" 2>&1)"; rc=$?
echo "EXIT: $rc"
echo "---evidence---"
printf '%s\n' "$out"
echo "---end---"
if [[ $rc -eq 0 ]]; then echo "RESULT: PASS"; else echo "RESULT: FAIL"; fi
exit $rc
```

- [ ] **Step 4: Make executable and run test to verify it passes**

Run:
```bash
chmod +x plugins/clone-build/skills/clone-build/scripts/run-gate.sh
bash plugins/clone-build/tests/test-run-gate.sh
```
Expected: all PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-build/skills/clone-build/scripts/run-gate.sh \
        plugins/clone-build/tests/test-run-gate.sh
git commit -m "feat(clone-build): add run-gate.sh gate chokepoint"
```

---

### Task 4: `gen-build-plan.py` — spec + artifacts → build-plan.json

**Files:**
- Create: `plugins/clone-build/skills/clone-build/scripts/gen-build-plan.py`
- Create: `plugins/clone-build/tests/fixtures/work-complete/design-tokens.json`
- Create: `plugins/clone-build/tests/fixtures/work-complete/payloads.json`
- Create: `plugins/clone-build/tests/fixtures/work-complete/nav-graph.json`
- Create: `plugins/clone-build/tests/fixtures/work-complete/logic-signals.json`
- Create: `plugins/clone-build/tests/fixtures/work-complete/screenshots/01.png`
- Create: `plugins/clone-build/tests/fixtures/work-incomplete/design-tokens.json`
- Test: `plugins/clone-build/tests/test-gen-build-plan.py`

**Interfaces:**
- Consumes: positional `spec` path; `--work <artifacts dir>`; `--out <build-plan.json>`. Reuses Task 1's branch logic (reimplemented in Python for determinism — no subprocess).
- Produces: writes `build-plan.json` with top-level keys `package, title, branch, substack, generated_from, gaps, tasks`. Each task: `id, type, title, inputs (absolute paths), instructions, gate {kind, command:"", pass_when}, status, depends_on`. Required artifacts: `design-tokens.json`, `payloads.json`, `nav-graph.json`, and ≥1 `screenshots/*.png`. Missing/empty → a `gaps` entry; dependent screen/design/api tasks get status `needs-human-input`. Deterministic: all collections sorted; same inputs → identical bytes.

- [ ] **Step 1: Create the artifact fixtures**

`plugins/clone-build/tests/fixtures/work-complete/design-tokens.json`:
```json
{ "colors": { "primary": "#3366FF" }, "type": { "base": 16 } }
```

`plugins/clone-build/tests/fixtures/work-complete/payloads.json`:
```json
[
  { "host": "api.acme.com", "method": "POST", "path": "/login" },
  { "host": "api.acme.com", "method": "GET",  "path": "/notes" }
]
```

`plugins/clone-build/tests/fixtures/work-complete/nav-graph.json`:
```json
{
  "nodes": [
    { "id": "login", "label": "Login" },
    { "id": "home",  "label": "Home" }
  ],
  "edges": [ { "from": "login", "to": "home", "trigger": "tap_login" } ]
}
```

`plugins/clone-build/tests/fixtures/work-complete/logic-signals.json`:
```json
{ "signals": [ { "name": "validateEmail" } ] }
```

`plugins/clone-build/tests/fixtures/work-incomplete/design-tokens.json`:
```json
{ "colors": { "primary": "#000000" } }
```

Create the screenshot placeholder (content is irrelevant — only the `.png` filename matters to the generator):
```bash
mkdir -p plugins/clone-build/tests/fixtures/work-complete/screenshots
printf 'PNGPLACEHOLDER\n' > plugins/clone-build/tests/fixtures/work-complete/screenshots/01.png
```

- [ ] **Step 2: Write the failing test**

`plugins/clone-build/tests/test-gen-build-plan.py`:
```python
#!/usr/bin/env python3
import json, subprocess, sys, os, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-build", "scripts", "gen-build-plan.py")
SPEC = os.path.join(HERE, "fixtures", "spec-app.md")
WORK_OK = os.path.join(HERE, "fixtures", "work-complete")
WORK_BAD = os.path.join(HERE, "fixtures", "work-incomplete")

def gen(spec, work):
    out = os.path.join(tempfile.mkdtemp(), "build-plan.json")
    subprocess.check_output([sys.executable, SCRIPT, spec, "--work", work, "--out", out])
    with open(out) as f:
        return f.read(), json.loads(open(out).read())

def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    raw1, d = gen(SPEC, WORK_OK)
    ids = [t["id"] for t in d["tasks"]]
    gate = {t["id"]: t["gate"]["kind"] for t in d["tasks"]}
    typ  = {t["id"]: t["type"] for t in d["tasks"]}

    check("branch app", d["branch"] == "app")
    check("substack flutter", d["substack"] == "flutter")
    check("package parsed", d["package"] == "com.acme.notes")
    check("title parsed", d["title"] == "Acme Notes")
    check("no gaps when complete", d["gaps"] == [])

    check("scaffold first", ids[0] == "scaffold")
    check("design-system present", "design-system" in ids)
    # screens sorted by node id: home < login
    check("screen-home before screen-login",
          ids.index("screen-home") < ids.index("screen-login"))
    # endpoints sorted by (host,path,method): /login < /notes
    check("api-01 present", "api-01" in ids)
    check("api-02 present", "api-02" in ids)
    check("logic task present", "logic-validateemail" in ids)
    check("integration last", ids[-1] == "integration")

    check("scaffold gate build", gate["scaffold"] == "build")
    check("design gate build", gate["design-system"] == "build")
    check("screen gate visual-diff", gate["screen-home"] == "visual-diff")
    check("ui type for app", typ["screen-home"] == "ui")
    check("api gate tdd", gate["api-01"] == "tdd")
    check("logic gate tdd", gate["logic-validateemail"] == "tdd")
    check("integration gate launch-crash", gate["integration"] == "launch-crash")

    # absolute paths in inputs
    check("inputs absolute", all(
        all(os.path.isabs(p) for p in t["inputs"]) for t in d["tasks"]))
    # integration depends on screens + apis
    integ = [t for t in d["tasks"] if t["id"] == "integration"][0]
    check("integration depends on screens",
          "screen-home" in integ["depends_on"] and "api-01" in integ["depends_on"])
    # gate command empty in skeleton
    check("gate command empty", all(t["gate"]["command"] == "" for t in d["tasks"]))

    # determinism: regenerate, identical bytes
    raw2, _ = gen(SPEC, WORK_OK)
    check("deterministic output", raw1 == raw2)

    # incomplete artifacts → gaps + needs-human-input
    _, bad = gen(SPEC, WORK_BAD)
    gap_arts = {g["artifact"] for g in bad["gaps"]}
    check("gap: payloads.json", "payloads.json" in gap_arts)
    check("gap: nav-graph.json", "nav-graph.json" in gap_arts)
    check("gap: screenshots", "screenshots/" in gap_arts)
    dmap = {t["id"]: t["status"] for t in bad["tasks"]}
    check("design-system needs-human-input", dmap["design-system"] == "pending")  # tokens present
    # screens come from nav-graph which is missing → no screen tasks, but design ok
    check("no screen tasks when nav missing",
          not any(i.startswith("screen-") for i in dmap))

    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 plugins/clone-build/tests/test-gen-build-plan.py`
Expected: FAIL (script missing / cannot import).

- [ ] **Step 4: Write the script**

`plugins/clone-build/skills/clone-build/scripts/gen-build-plan.py`:
```python
#!/usr/bin/env python3
"""Generate build-plan.json (task graph) from a clone-build-spec.md + $WORK artifacts.

Deterministic: no clock, no randomness — same inputs produce identical output.
Branch-agnostic core. Gate KIND is set per task type; gate COMMAND is left empty
here and filled later by the branch build guide.
"""
import argparse, json, os, re, sys

REQUIRED = ["design-tokens.json", "payloads.json", "nav-graph.json"]

# task type -> (gate kind, pass_when)
GATE = {
    "scaffold":    ("build",        "project compiles, 0 errors"),
    "design":      ("build",        "design tokens applied; compiles, 0 errors"),
    "ui":          ("visual-diff",  "screenshot matches target >= threshold; build+launch no crash"),
    "scene":       ("visual-diff",  "scene screenshot matches target; compiles, 0 console errors"),
    "api":         ("tdd",          "contract test vs payloads.json shape exits 0"),
    "logic":       ("tdd",          "failing test written first, then test exits 0"),
    "integration": ("launch-crash", "app/scene launches; no fatal in log for N seconds"),
}


def detect_branch(spec_text):
    m = re.search(r'(?im)^.*selected stack.*$', spec_text)
    line = m.group(0).lower() if m else ""
    if "unity" in line or "il2cpp" in line:
        return "game", "unity"
    if "flutter" in line:
        return "app", "flutter"
    if re.search(r'react.?native', line):
        return "app", "react-native"
    if re.search(r'native|kotlin|compose|jetpack', line):
        return "app", "native-android"
    return "app", "unknown"


def field(spec_text, label):
    m = re.search(r'\*\*%s:\*\*\s*([^\n·|]+)' % re.escape(label), spec_text)
    return m.group(1).strip() if m else ""


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def gate(task_type):
    k, pw = GATE[task_type]
    return {"kind": k, "command": "", "pass_when": pw}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec_path = os.path.abspath(args.spec)
    work = os.path.abspath(args.work)
    with open(spec_path) as f:
        spec_text = f.read()

    branch, substack = detect_branch(spec_text)
    package = field(spec_text, "Package") or "unknown"
    mt = re.search(r'(?m)^#\s+Clone Build Spec\s*[—-]\s*(.+)$', spec_text)
    title = mt.group(1).strip() if mt else package

    # --- gaps / completeness ---
    gaps = []
    for req in REQUIRED:
        p = os.path.join(work, req)
        if not os.path.exists(p):
            gaps.append({"artifact": req, "reason": "missing"})
        else:
            d = load_json(p)
            if d in (None, [], {}):
                gaps.append({"artifact": req, "reason": "empty or invalid JSON"})

    shots_dir = os.path.join(work, "screenshots")
    shots = sorted(f for f in os.listdir(shots_dir)
                   if f.lower().endswith(".png")) if os.path.isdir(shots_dir) else []
    if not shots:
        gaps.append({"artifact": "screenshots/", "reason": "no PNG screenshots"})

    missing = {g["artifact"] for g in gaps}

    def status_for(deps):
        return "needs-human-input" if any(a in missing for a in deps) else "pending"

    dtokens = os.path.join(work, "design-tokens.json")
    payloads_path = os.path.join(work, "payloads.json")
    nav_path = os.path.join(work, "nav-graph.json")
    logic_path = os.path.join(work, "logic-signals.json")
    logic_digest = os.path.join(work, "logic-digest.md")

    tasks = []

    # 1. scaffold
    tasks.append({
        "id": "scaffold", "type": "scaffold",
        "title": "Scaffold buildable %s project" % branch,
        "inputs": [spec_path],
        "instructions": "Create an empty buildable project per the %s branch guide "
                        "(substack: %s)." % (branch, substack),
        "gate": gate("scaffold"), "status": "pending", "depends_on": [],
    })

    # 2. design-system
    tasks.append({
        "id": "design-system", "type": "design",
        "title": "Implement design system",
        "inputs": [dtokens, spec_path],
        "instructions": "Apply the color/type/spacing/radius tokens from "
                        "design-tokens.json as the app theme.",
        "gate": gate("design"),
        "status": status_for(["design-tokens.json"]),
        "depends_on": ["scaffold"],
    })

    # 3. screens from nav-graph nodes
    nav = load_json(nav_path) or {}
    nodes = nav.get("nodes", []) if isinstance(nav, dict) else []
    screen_type = "scene" if branch == "game" else "ui"
    screen_ids = []
    for node in sorted(nodes, key=lambda n: str(n.get("id", ""))):
        nid = str(node.get("id", ""))
        if not nid:
            continue
        tid = "screen-%s" % nid
        screen_ids.append(tid)
        tasks.append({
            "id": tid, "type": screen_type,
            "title": "Build %s screen: %s" % (branch, node.get("label", nid)),
            "inputs": [spec_path, dtokens, shots_dir],
            "instructions": "Build the '%s' screen to match its target screenshot "
                            "and the spec screen entry." % nid,
            "gate": gate(screen_type),
            "status": status_for(["nav-graph.json", "screenshots/"]),
            "depends_on": ["design-system"],
        })

    # 4. api tasks from payloads
    payloads = load_json(payloads_path) or []
    eps = payloads if isinstance(payloads, list) else payloads.get("endpoints", [])
    def ep_key(e):
        return (str(e.get("host", "")), str(e.get("path", "")), str(e.get("method", "")))
    api_ids = []
    for i, ep in enumerate(sorted(eps, key=ep_key), 1):
        tid = "api-%02d" % i
        api_ids.append(tid)
        tasks.append({
            "id": tid, "type": "api",
            "title": "Implement API client: %s %s" % (ep.get("method", "?"), ep.get("path", "?")),
            "inputs": [payloads_path],
            "instructions": "Implement and contract-test the %s %s call per "
                            "payloads.json." % (ep.get("method", "?"), ep.get("path", "?")),
            "gate": gate("api"),
            "status": status_for(["payloads.json"]),
            "depends_on": ["scaffold"],
        })

    # 5. logic tasks (optional artifact)
    logic = load_json(logic_path)
    if isinstance(logic, dict):
        signals = logic.get("signals", logic.get("items", []))
        names = []
        if isinstance(signals, list):
            for s in signals:
                names.append(str(s.get("name", s) if isinstance(s, dict) else s))
        for name in sorted(set(names)):
            safe = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or "rule"
            tasks.append({
                "id": "logic-%s" % safe, "type": "logic",
                "title": "Implement logic: %s" % name,
                "inputs": [logic_path, logic_digest],
                "instructions": "TDD the '%s' rule per logic-signals.json / "
                                "logic-digest.md." % name,
                "gate": gate("logic"), "status": "pending",
                "depends_on": ["scaffold"],
            })

    # 6. integration (always last)
    tasks.append({
        "id": "integration", "type": "integration",
        "title": "End-to-end integration verify",
        "inputs": [spec_path, nav_path],
        "instructions": "Build, launch, and walk every screen/flow; confirm no crash "
                        "and navigation matches nav-graph.json.",
        "gate": gate("integration"), "status": "pending",
        "depends_on": screen_ids + api_ids,
    })

    plan = {
        "package": package, "title": title, "branch": branch, "substack": substack,
        "generated_from": spec_path, "gaps": gaps, "tasks": tasks,
    }
    with open(args.out, "w") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")
    print("wrote %s (%d tasks, %d gaps)" % (args.out, len(tasks), len(gaps)))


main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 plugins/clone-build/tests/test-gen-build-plan.py`
Expected: all PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-build/skills/clone-build/scripts/gen-build-plan.py \
        plugins/clone-build/tests/test-gen-build-plan.py \
        plugins/clone-build/tests/fixtures/work-complete \
        plugins/clone-build/tests/fixtures/work-incomplete
git commit -m "feat(clone-build): add gen-build-plan.py + artifact fixtures"
```

---

### Task 5: References — plan-contract.md, gate-catalog.md, build-report-template.md

**Files:**
- Create: `plugins/clone-build/skills/clone-build/references/plan-contract.md`
- Create: `plugins/clone-build/skills/clone-build/references/gate-catalog.md`
- Create: `plugins/clone-build/skills/clone-build/references/build-report-template.md`
- Test: `plugins/clone-build/tests/test-references-content.sh`

**Interfaces:**
- Consumes: nothing (static docs).
- Produces: the documented contracts the scripts and branch guides share. The test asserts each file carries the required vocabulary so later plans can rely on it.

- [ ] **Step 1: Write the failing test**

`plugins/clone-build/tests/test-references-content.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
R="$HERE/../skills/clone-build/references"
fail=0
need() { local f="$1" pat="$2"; if grep -qiF "$pat" "$f"; then echo "PASS: $(basename "$f") has '$pat'"; else echo "FAIL: $(basename "$f") missing '$pat'"; fail=1; fi; }

for kw in "depends_on" "needs-human-input" "forcing rule" "pass_when" "gate"; do
  need "$R/plan-contract.md" "$kw"
done
for kw in "visual-diff" "launch-crash" "build" "tdd"; do
  need "$R/gate-catalog.md" "$kw"
done
for kw in "SKIP" "gate" "visual-diff"; do
  need "$R/build-report-template.md" "$kw"
done

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-build/tests/test-references-content.sh`
Expected: FAIL (files missing).

- [ ] **Step 3: Write `plan-contract.md`**

`plugins/clone-build/skills/clone-build/references/plan-contract.md`:
```markdown
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
```

- [ ] **Step 4: Write `gate-catalog.md`**

`plugins/clone-build/skills/clone-build/references/gate-catalog.md`:
```markdown
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
```

- [ ] **Step 5: Write `build-report-template.md`**

`plugins/clone-build/skills/clone-build/references/build-report-template.md`:
```markdown
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `bash plugins/clone-build/tests/test-references-content.sh`
Expected: all PASS, exit 0.

- [ ] **Step 7: Commit**

```bash
git add plugins/clone-build/skills/clone-build/references \
        plugins/clone-build/tests/test-references-content.sh
git commit -m "feat(clone-build): add plan-contract, gate-catalog, report template"
```

---

### Task 6: `SKILL.md` — shared 6-phase spine

**Files:**
- Create: `plugins/clone-build/skills/clone-build/SKILL.md`
- Test: `plugins/clone-build/tests/test-skill-phases.sh`

**Interfaces:**
- Consumes: at runtime, `clone-build-spec.md` + `$WORK/` artifacts (produced by clone-app Phase 8).
- Produces: the orchestration prose. The test asserts all six phase markers, both branch-guide references, the contract references, and the execution handoff string are present.

- [ ] **Step 1: Write the failing test**

`plugins/clone-build/tests/test-skill-phases.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-build/SKILL.md"
fail=0
need() { if grep -qF "$1" "$S"; then echo "PASS: SKILL has '$1'"; else echo "FAIL: SKILL missing '$1'"; fail=1; fi; }

for p in "## P0" "## P1" "## P2" "## P3" "## P4" "## P5"; do need "$p"; done
need "detect-branch.sh"
need "preflight.sh"
need "gen-build-plan.py"
need "run-gate.sh"
need "game-build-guide.md"
need "app-build-guide.md"
need "plan-contract.md"
need "gate-catalog.md"
need "subagent-driven-development"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-build/tests/test-skill-phases.sh`
Expected: FAIL (SKILL.md missing).

- [ ] **Step 3: Write `SKILL.md`**

`plugins/clone-build/skills/clone-build/SKILL.md`:
```markdown
---
description: Turn a clone-build-spec.md plus its $WORK/ artifacts into running, verified, production-ready code — for apps (Flutter / native Android / RN) or games (Unity via MCP). Drives a deterministic task graph where every task is gated by a machine-checkable build / TDD / visual-diff / launch check, so even a weak model in a fresh session converges on a correct clone. Use after clone-app Phase 8 has produced a build spec and the user chose "Build it". 中文触发词：克隆构建、生成可运行代码、构建克隆
trigger: build the clone|clone build|generate the app from spec|build from clone-build-spec|implement the clone|克隆构建|生成可运行代码
---

# Clone Build — Spec to Prod-Ready Code

Take `clone-build-spec.md` and the `$WORK/` artifacts from clone-app Phase 8, scaffold
a buildable project, generate a gated task graph, and drive it to verified,
production-ready code. Games go through the Unity-MCP branch; apps through the
Flutter / native-Android / RN branch. The two branches share this spine; their
specifics live in `references/{game,app}-build-guide.md`, loaded on demand.

This skill orchestrates 6 phases (P0–P5). Deterministic steps are factored into
helper scripts under `${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/`.

## Legal note
Only build clones you are authorized to (your own apps, lawful interoperability /
research). The clone-app legal note still governs which apps may be analyzed at all.
Extracted game art is reference-only outside authorized use — recreate in-style.

## P0: Preflight & spec load
Locate the build spec (default `./work/<pkg>/clone-build-spec.md`) and its `$WORK`
artifact dir. If either is missing, stop and tell the user to run clone-app Phase 8
first.

Detect the branch:
```bash
read BRANCH SUBSTACK < <(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/detect-branch.sh "$SPEC")
```
Probe the toolchain:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/preflight.sh --out "$WORK/preflight.json"
```
Then load **only** the matching branch guide: `references/app-build-guide.md` for
`app`, `references/game-build-guide.md` for `game`. (These are added in later plans;
if absent, note the gap and continue with the spine.)

## P1: Project scaffold
Per the loaded branch guide, scaffold an empty **buildable** project into
`$WORK/clone/`. For `game`, this is a headless Unity CLI `-createProject` plus the
MCP-for-Unity package, then a connection check. For `app`, `flutter create` / a
gradle template / `react-native init`. Missing prerequisites → print exact setup
guidance and pause; never half-fail.

## P2: Plan generation
Generate the gated task graph from the spec + artifacts:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/gen-build-plan.py \
  "$SPEC" --work "$WORK" --out "$WORK/build-plan.json"
```
The schema and the generation rules are in `references/plan-contract.md`; the gate
kind per task type is in `references/gate-catalog.md`. Any entry in the plan's
`gaps` array, or any task with status `needs-human-input`, is surfaced to the user
before execution — the build never silently fills a hole.

## P3: Execution loop
Execute the plan task-by-task using **superpowers:subagent-driven-development**: a
fresh subagent per task implements it, then runs its gate through
`${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/run-gate.sh --kind <kind>
--command "<cmd>"`. The forcing rule (see `plan-contract.md`) holds: a task is
`done` only when `run-gate.sh` printed `RESULT: PASS`. A reviewer subagent re-checks
the gate evidence before dependents unblock. Per-task status is written back to
`build-plan.json`, so a dropped session resumes by skipping done-and-gated tasks.
If subagent-driven-development is unavailable, run tasks inline but still gate each
through `run-gate.sh`.

## P4: Integration verify
Run the `integration` task: full build, launch, and an end-to-end walk of every
screen/flow, confirming no crash and that navigation matches `nav-graph.json`. For
the app branch this is the always-on hard gate (build + install + launch + no fatal
log); the visual pass runs when an emulator/device is present, else it is SKIP.

## P5: Build report
Write `$WORK/build-report-<YYYY-MM-DD>.md` from
`references/build-report-template.md`: tasks done, gate evidence, visual-fidelity
verdicts (or SKIP + reason), remaining `needs-human-input` items, and next manual
steps.

## Error Handling Summary
| Scenario | Action |
|---|---|
| Spec / artifacts missing | stop; tell user to run clone-app Phase 8 first |
| Branch guide file absent | note the gap, continue with the spine |
| Toolchain missing (Unity / flutter / gradle / node) | print setup guidance, pause |
| MCP not connected after Unity scaffold | guidance, poll editor state, pause |
| Gate fails | task stays open; subagent retries; after N retries escalate with evidence |
| Visual-diff below threshold | iterate up to N, then flag for user review; never force-pass |
| Emulator absent (app) | hard gate still runs; visual = SKIP + guidance |
| subagent-driven-development unavailable | run tasks inline, still gate via run-gate.sh |
| Mid-run session death | resume from build-plan.json status — skip done-and-gated tasks |
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash plugins/clone-build/tests/test-skill-phases.sh`
Expected: all PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-build/skills/clone-build/SKILL.md \
        plugins/clone-build/tests/test-skill-phases.sh
git commit -m "feat(clone-build): add SKILL.md 6-phase spine"
```

---

### Task 7: Plugin metadata, command, README, marketplace entry

**Files:**
- Create: `plugins/clone-build/.claude-plugin/plugin.json`
- Create: `plugins/clone-build/commands/clone-build.md`
- Create: `plugins/clone-build/README.md`
- Modify: `.claude-plugin/marketplace.json` (append fourth plugin entry)

**Interfaces:**
- Consumes: nothing.
- Produces: installable plugin identity. `/plugin install clone-build@clone-app-skill` resolves via the marketplace `name`; the plugin's own `plugin.json` carries `name: clone-build`.

- [ ] **Step 1: Write `plugin.json`**

`plugins/clone-build/.claude-plugin/plugin.json`:
```json
{
  "name": "clone-build",
  "version": "0.1.0",
  "description": "Turn a clone-build-spec.md plus its $WORK artifacts into running, verified, production-ready code for apps (Flutter / native / RN) or games (Unity via MCP), driving a gated task graph.",
  "author": {
    "name": "masa2146"
  },
  "repository": "https://github.com/masa2146/clone-app-skill",
  "license": "Apache-2.0",
  "keywords": ["clone", "build", "codegen", "unity-mcp", "flutter", "verification"],
  "skills": "./skills/",
  "commands": "./commands/"
}
```

- [ ] **Step 2: Write the command**

`plugins/clone-build/commands/clone-build.md`:
```markdown
---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
description: Build a verified, prod-ready clone from a clone-build-spec.md (app or game)
user-invocable: true
argument-hint: <path to clone-build-spec.md or ./work/<pkg>>
argument: path to the build spec or work dir (optional)
---

# /clone-build

Drive the clone-build skill: spec → scaffold → gated task graph → verified code.

## Instructions

Follow the clone-build skill workflow in
`${CLAUDE_PLUGIN_ROOT}/skills/clone-build/SKILL.md` exactly, phases P0 through P5.

### Step 1: Locate the spec
If the user passed a path, use it. Otherwise look for
`./work/<pkg>/clone-build-spec.md`. If none exists, tell the user to run clone-app
Phase 8 first.

### Step 2: Run the skill
Execute P0 → P5. Surface the plan's `gaps` and any `needs-human-input` tasks before
execution. Honor the Error Handling Summary table in SKILL.md.

### Step 3: Deliver
Ensure `./work/<pkg>/build-report-<date>.md` is written and summarize the outcome.
```

- [ ] **Step 3: Write the README**

`plugins/clone-build/README.md`:
```markdown
# clone-build

The build/verify stage of the **discover → analyze → build** pipeline
(`market-research → clone-app → clone-build`). Takes the `clone-build-spec.md` and
`$WORK/` artifacts produced by clone-app Phase 8 and drives them to running,
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
- `preflight.sh` — probe Unity / flutter / gradle / node / adb → JSON.
- `gen-build-plan.py` — spec + artifacts → `build-plan.json` (deterministic).
- `run-gate.sh` — single gate-execution chokepoint.

## Tests
```bash
bash plugins/clone-build/tests/run-all.sh
```
Offline fixtures only — no live Unity / emulator / network.

## Status
Branch-agnostic core. The app branch, game branch, and clone-app Phase-7 wiring land
in later plans.
```

- [ ] **Step 4: Append the marketplace entry**

In `.claude-plugin/marketplace.json`, the `plugins` array currently ends with the
`market-research` object. Add a comma after its closing `}` and append this fourth
entry before the array's closing `]`:

```json
    {
      "name": "clone-build",
      "source": "./plugins/clone-build",
      "description": "Build a verified, prod-ready clone (app or game) from a clone-build-spec.md, driving a gated task graph.",
      "version": "0.1.0",
      "author": {
        "name": "masa2146"
      },
      "repository": "https://github.com/masa2146/clone-app-skill",
      "license": "Apache-2.0",
      "keywords": ["clone", "build", "codegen", "unity-mcp", "verification"],
      "category": "security"
    }
```

- [ ] **Step 5: Validate JSON and the marketplace entry**

Run:
```bash
python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); n=[p['name'] for p in d['plugins']]; assert 'clone-build' in n, n; print('PASS', n)"
python3 -c "import json; json.load(open('plugins/clone-build/.claude-plugin/plugin.json')); print('PASS plugin.json')"
```
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-build/.claude-plugin/plugin.json \
        plugins/clone-build/commands/clone-build.md \
        plugins/clone-build/README.md \
        .claude-plugin/marketplace.json
git commit -m "feat(clone-build): add plugin metadata, command, README, marketplace entry"
```

---

### Task 8: `smoke-structure.sh` + `run-all.sh` + full-suite green

**Files:**
- Create: `plugins/clone-build/tests/smoke-structure.sh`
- Create: `plugins/clone-build/tests/run-all.sh`

**Interfaces:**
- Consumes: every file created in Tasks 1–7.
- Produces: a structural smoke test (files present, scripts executable, JSON valid, plugin in marketplace) and an aggregating runner, mirroring the clone-app test layout.

- [ ] **Step 1: Write `smoke-structure.sh`**

`plugins/clone-build/tests/smoke-structure.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # repo root
P="$ROOT/plugins/clone-build"
fail=0
must_exist() { [[ -e "$1" ]] && echo "PASS exists: ${1#$ROOT/}" || { echo "FAIL missing: ${1#$ROOT/}"; fail=1; }; }
must_exec()  { [[ -x "$1" ]] && echo "PASS exec: ${1#$ROOT/}"   || { echo "FAIL not exec: ${1#$ROOT/}"; fail=1; }; }

must_exist "$P/.claude-plugin/plugin.json"
must_exist "$P/skills/clone-build/SKILL.md"
must_exist "$P/commands/clone-build.md"
must_exist "$P/README.md"

for s in detect-branch.sh preflight.sh run-gate.sh; do
  must_exist "$P/skills/clone-build/scripts/$s"; must_exec "$P/skills/clone-build/scripts/$s"
done
must_exist "$P/skills/clone-build/scripts/gen-build-plan.py"
for r in plan-contract gate-catalog build-report-template; do
  must_exist "$P/skills/clone-build/references/$r.md"
done

# JSON validity
python3 -c "import json;json.load(open('$P/.claude-plugin/plugin.json'));json.load(open('$ROOT/.claude-plugin/marketplace.json'))" \
  && echo "PASS json valid" || { echo "FAIL json invalid"; fail=1; }

# clone-build present in marketplace
python3 -c "
import json;d=json.load(open('$ROOT/.claude-plugin/marketplace.json'))
names=[p['name'] for p in d['plugins']]
assert 'clone-build' in names, names
print('PASS marketplace has clone-build')" || { echo "FAIL marketplace entry"; fail=1; }

# upstream untouched guard
if [[ -n "$(git -C "$ROOT" status --porcelain plugins/android-reverse-engineering/ 2>/dev/null)" ]]; then
  echo "FAIL upstream tree modified"; fail=1
else
  echo "PASS upstream untouched"
fi

exit $fail
```

- [ ] **Step 2: Write `run-all.sh`**

`plugins/clone-build/tests/run-all.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
fail=0

echo "=== smoke ==="
bash "$HERE/smoke-structure.sh" || fail=1

echo "=== bash tests ==="
for t in "$HERE"/test-*.sh; do
  echo "--- $(basename "$t") ---"
  bash "$t" || fail=1
done

echo "=== python tests ==="
for t in "$HERE"/test-*.py; do
  echo "--- $(basename "$t") ---"
  python3 "$t" || fail=1
done

echo
if [[ "$fail" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit $fail
```

- [ ] **Step 3: Make executable and run the full suite**

Run:
```bash
chmod +x plugins/clone-build/tests/smoke-structure.sh plugins/clone-build/tests/run-all.sh
bash plugins/clone-build/tests/run-all.sh
```
Expected: `ALL TESTS PASSED`, exit 0.

- [ ] **Step 4: Verify upstream is byte-identical**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: prints nothing.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-build/tests/smoke-structure.sh \
        plugins/clone-build/tests/run-all.sh
git commit -m "test(clone-build): add smoke-structure + run-all aggregator"
```

---

## Self-Review

**Spec coverage** (against `2026-06-30-clone-build-prod-ready-design.md`):
- §4 plugin layout → Tasks 1–8 create the full mirrored tree. ✓
- §5.1 SKILL.md spine P0–P5 → Task 6. ✓
- §5.1 references (plan-contract, gate-catalog, build-report-template) → Task 5. ✓ (Branch guides `game-build-guide.md` / `app-build-guide.md` are explicitly later plans; SKILL.md references them and tolerates absence.)
- §5.2 scripts (detect-branch, scaffold-*, gen-build-plan, run-gate, preflight) → Tasks 1–4 cover detect-branch, preflight, run-gate, gen-build-plan. `scaffold-unity.sh` / `scaffold-app.sh` are branch-specific → deferred to later plans by design (this plan is branch-agnostic core). ✓
- §6 task graph + gate contract → Task 4 (`gen-build-plan.py`) + Task 5 (`plan-contract.md`, `gate-catalog.md`). ✓
- §7.1 spec-completeness preflight → Task 4 gaps/needs-human-input logic + test. ✓
- §9 conventions (stdlib, determinism, test discipline) → enforced in every task. ✓
- §10 tests list → Tasks 1–8 create test-detect-branch, test-preflight, test-run-gate, test-gen-build-plan, test-references-content, test-skill-phases, smoke-structure, run-all. ✓
- Hard constraint (upstream untouched) → guarded in smoke-structure.sh (Task 8) and Task 8 Step 4. ✓

**Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N". Empty `gate.command` is an intentional, documented contract field (filled by later branch plans), not a plan placeholder.

**Type consistency:** vocabulary tokens (`game|app`; `unity|flutter|react-native|native-android|unknown`; task types; gate kinds `build|tdd|visual-diff|launch-crash`; statuses) are identical across detect-branch.sh, gen-build-plan.py, plan-contract.md, gate-catalog.md, SKILL.md, and all tests. Task ids (`scaffold`, `design-system`, `screen-<id>`, `api-NN`, `logic-<name>`, `integration`) match between the generator and the test assertions.
