# clone-app Fidelity Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deep "fidelity pass" to the clone-app skill that, when the user proceeds to build at the Phase 7 gate, extracts in-app logic, the real navigation graph, full API payloads, and an inferred backend design — producing a standalone fidelity report that (with the feasibility report) drives an exact / near-exact rebuild.

**Architecture:** No mode flag. Phases 0–6 run unchanged and yield the feasibility report. The Phase 7 "proceed to build a plan?" gate triggers a Phase 8 fidelity subagent that reads what Phase 2 already decompiled to `$WORK/output` (no re-decompile), runs two new extractor scripts plus deeper RE, writes new digest artifacts, emits `fidelity-report-<date>.md`, assembles the fidelity build spec, and hands both reports to `writing-plans`.

**Tech Stack:** Bash 4+, stdlib-only Python 3 (`os`, `re`, `json`, `glob`, `xml.etree`), Markdown skill/reference docs. No pip, no network.

## Global Constraints

- `plugins/android-reverse-engineering/` stays byte-identical — never modify it. Before every commit, `git status --porcelain plugins/android-reverse-engineering/` must print nothing.
- All new Python is **stdlib-only** (`urllib`/`json`/`re`/`os`/`glob`/`xml.etree`); no pip, no virtualenv.
- All scripts start `#!/usr/bin/env bash` or `#!/usr/bin/env python3`; bash scripts assume **bash 4+**, invoked as `bash <path>`.
- Tests run **offline** against `tests/fixtures/` only — never hit the network.
- Bash tests use `set -uo pipefail` (not `-e`) and aggregate failures into a `fail` var so every assertion runs.
- Working dir convention is `./work/{package}/` relative to the user's cwd, never inside the plugin.
- Commits follow Conventional Commits scoped to the plugin: `feat(clone-app): …`, `test(clone-app): …`, `docs(clone-app): …`.
- New scripts live under `plugins/clone-app/skills/clone-app/scripts/`; new references under `plugins/clone-app/skills/clone-app/references/`; tests and fixtures under `plugins/clone-app/tests/`.
- `tests/run-all.sh` globs `test-*.sh` and `test-*.py` automatically — new test files self-register; no edit to `run-all.sh` is needed.

---

## File Structure

**New scripts** (`plugins/clone-app/skills/clone-app/scripts/`):
- `extract-logic.py` — emits a JSON in-app-logic signals inventory from the decompiled source tree.
- `extract-nav-graph.py` — emits `nav-graph.json` from Navigation XML + Compose `NavHost` routes.

**New references** (`plugins/clone-app/skills/clone-app/references/`):
- `fidelity-pass-guide.md` — what the Phase 8 fidelity pass does + the two-report model.
- `logic-capture-guide.md` — how the subagent distills `logic-digest.md` (framework-aware confidence).
- `backend-recon-guide.md` — how to turn the observed contract into an inferred backend design.

**Modified references:**
- `re-digest-contract.md` — document the three fidelity artifacts + the Tier-2-on-all-first-party rule.
- `clone-build-spec-template.md` — add §3b user-flow diagrams and §5b backend rebuild spec; deepen §3/§4/§5/§6.
- `unity-re-guide.md` — game-mechanic / formula extraction depth.

**Modified orchestrator:**
- `SKILL.md` — Phase 7 gate triggers the fidelity pass; Phase 8 fidelity subagent + two-report output.

**New tests + fixtures** (`plugins/clone-app/tests/`):
- `test-extract-logic.py` + `fixtures/logic-sample/`
- `test-extract-nav-graph.py` + `fixtures/nav-sample/`
- Extend `smoke-structure.sh`, `test-references-content.sh`, `test-skill-phases.sh`.

---

### Task 1: `extract-logic.py` — in-app logic signals inventory

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/extract-logic.py`
- Create fixture: `plugins/clone-app/tests/fixtures/logic-sample/com/example/LoginViewModel.kt`
- Create fixture: `plugins/clone-app/tests/fixtures/logic-sample/com/example/SyncUseCase.kt`
- Create fixture: `plugins/clone-app/tests/fixtures/logic-sample/com/example/UserEntity.kt`
- Create fixture: `plugins/clone-app/tests/fixtures/logic-sample/com/example/UserDao.kt`
- Create fixture: `plugins/clone-app/tests/fixtures/logic-sample/com/example/Status.kt`
- Test: `plugins/clone-app/tests/test-extract-logic.py`

**Interfaces:**
- Consumes: nothing (leaf script).
- Produces: CLI `python3 extract-logic.py <root> [--out FILE]`. Stdout (or `--out`) is a JSON object with keys `root`, `viewmodels`, `usecases`, `validation`, `state_enums`, `room_entities`, `room_daos`. Each of `viewmodels`/`usecases`/`room_entities`/`room_daos` is a list of `{"file": <relpath>, "name": <class>}`; `validation` is a list of `{"file", "line", "snippet"}`; `state_enums` is a list of `{"file", "name"}`. Consumed later by the Phase 8 subagent (Task 7) and named in `re-digest-contract.md` (Task 4).

- [ ] **Step 1: Create the fixture source tree**

`plugins/clone-app/tests/fixtures/logic-sample/com/example/LoginViewModel.kt`:
```kotlin
package com.example

class LoginViewModel : ViewModel() {
    fun validate(email: String): Boolean {
        return email.matches(Regex("^[^@]+@[^@]+$"))
    }
}
```

`plugins/clone-app/tests/fixtures/logic-sample/com/example/SyncUseCase.kt`:
```kotlin
package com.example

class SyncUseCase(private val repo: UserDao) {
    suspend operator fun invoke() = repo.all()
}
```

`plugins/clone-app/tests/fixtures/logic-sample/com/example/UserEntity.kt`:
```kotlin
package com.example

@Entity(tableName = "users")
data class UserEntity(val id: Long, val email: String)
```

`plugins/clone-app/tests/fixtures/logic-sample/com/example/UserDao.kt`:
```kotlin
package com.example

@Dao
interface UserDao {
    @Query("SELECT * FROM users")
    fun all(): List<UserEntity>
}
```

`plugins/clone-app/tests/fixtures/logic-sample/com/example/Status.kt`:
```kotlin
package com.example

enum class Status { IDLE, LOADING, ERROR }
```

- [ ] **Step 2: Write the failing test**

`plugins/clone-app/tests/test-extract-logic.py`:
```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "extract-logic.py")
ROOT = os.path.join(HERE, "fixtures", "logic-sample")

def run():
    out = subprocess.check_output([sys.executable, SCRIPT, ROOT])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    names = lambda lst: {x["name"] for x in lst}
    check("viewmodel detected", "LoginViewModel" in names(d["viewmodels"]))
    check("usecase detected", "SyncUseCase" in names(d["usecases"]))
    check("room entity detected", "UserEntity" in names(d["room_entities"]))
    check("room dao detected", "UserDao" in names(d["room_daos"]))
    check("state enum detected", "Status" in names(d["state_enums"]))
    check("validation flagged", any("matches" in v["snippet"] for v in d["validation"]))
    check("validation has file+line", all({"file","line","snippet"} <= set(v) for v in d["validation"]))
    for k in ["root","viewmodels","usecases","validation","state_enums","room_entities","room_daos"]:
        check(f"key present: {k}", k in d)
    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 plugins/clone-app/tests/test-extract-logic.py`
Expected: FAIL — script does not exist yet (`FileNotFoundError` / non-zero exit).

- [ ] **Step 4: Write the script**

`plugins/clone-app/skills/clone-app/scripts/extract-logic.py`:
```python
#!/usr/bin/env python3
"""Surface in-app logic signals from a decompiled APK source tree.

Walks .java/.kt sources and flags ViewModel/use-case classes, input-validation
calls, state-machine enums/sealed classes, and Room @Entity/@Dao declarations.
Stdlib-only. Emits a JSON signals inventory on stdout (or --out FILE); the
Phase 8 fidelity subagent distills it (plus the sources) into logic-digest.md.
"""
import os, re, json, argparse

SRC_EXT = (".java", ".kt")
VALIDATION_PAT = re.compile(r'(Pattern\.compile|\.matches\(|isValid|require\(|Validators?\.)')

def _iter_sources(root):
    for dp, _, files in os.walk(root):
        for fn in files:
            if fn.endswith(SRC_EXT):
                yield os.path.join(dp, fn)

def extract(root):
    vms, ucs, vals, enums, entities, daos = [], [], [], [], [], []
    for path in _iter_sources(root):
        name = os.path.splitext(os.path.basename(path))[0]
        rel = os.path.relpath(path, root)
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if name.endswith("ViewModel"):
            vms.append({"file": rel, "name": name})
        if name.endswith(("UseCase", "Interactor")):
            ucs.append({"file": rel, "name": name})
        for i, line in enumerate(text.splitlines(), 1):
            if VALIDATION_PAT.search(line):
                vals.append({"file": rel, "line": i, "snippet": line.strip()[:160]})
        for m in re.finditer(r'\b(?:enum|sealed)\s+class\s+(\w+)', text):
            enums.append({"file": rel, "name": m.group(1)})
        for m in re.finditer(r'\benum\s+(\w+)\s*\{', text):
            enums.append({"file": rel, "name": m.group(1)})
        if re.search(r'@Entity\b', text):
            entities.append({"file": rel, "name": name})
        if re.search(r'@Dao\b', text):
            daos.append({"file": rel, "name": name})
    return {
        "root": root,
        "viewmodels": vms,
        "usecases": ucs,
        "validation": vals,
        "state_enums": enums,
        "room_entities": entities,
        "room_daos": daos,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="decompile output root (sources)")
    ap.add_argument("--out")
    args = ap.parse_args()
    text = json.dumps(extract(args.root), indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 plugins/clone-app/tests/test-extract-logic.py`
Expected: PASS on every line; exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/skills/clone-app/scripts/extract-logic.py \
        plugins/clone-app/tests/test-extract-logic.py \
        plugins/clone-app/tests/fixtures/logic-sample/
git commit -m "feat(clone-app): extract-logic.py — in-app logic signals inventory"
```

---

### Task 2: `extract-nav-graph.py` — navigation graph

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/extract-nav-graph.py`
- Create fixture: `plugins/clone-app/tests/fixtures/nav-sample/res/navigation/nav_graph.xml`
- Test: `plugins/clone-app/tests/test-extract-nav-graph.py`

**Interfaces:**
- Consumes: nothing (leaf script).
- Produces: CLI `python3 extract-nav-graph.py <root> [--out FILE]`. Stdout (or `--out`) is a JSON object `{"root", "framework", "nodes", "edges"}` where `framework` ∈ `navigation-xml`/`compose`/`unknown`, `nodes` is a list of `{"id","label","kind","source"}`, `edges` is a list of `{"from","to","trigger","source"}`. Consumed later by the Phase 8 subagent (Task 7) and named in `re-digest-contract.md` (Task 4).

- [ ] **Step 1: Create the fixture**

`plugins/clone-app/tests/fixtures/nav-sample/res/navigation/nav_graph.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<navigation xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:id="@+id/nav_graph"
    app:startDestination="@id/loginFragment">
    <fragment
        android:id="@+id/loginFragment"
        android:name="com.example.LoginFragment">
        <action
            android:id="@+id/action_login_to_home"
            app:destination="@id/homeFragment" />
    </fragment>
    <fragment
        android:id="@+id/homeFragment"
        android:name="com.example.HomeFragment" />
</navigation>
```

- [ ] **Step 2: Write the failing test**

`plugins/clone-app/tests/test-extract-nav-graph.py`:
```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "extract-nav-graph.py")
ROOT = os.path.join(HERE, "fixtures", "nav-sample")

def run():
    out = subprocess.check_output([sys.executable, SCRIPT, ROOT])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    ids = {n["id"] for n in d["nodes"]}
    check("framework navigation-xml", d["framework"] == "navigation-xml")
    check("login node", "loginFragment" in ids)
    check("home node", "homeFragment" in ids)
    check("node has name label", any(n["label"] == "com.example.LoginFragment" for n in d["nodes"]))
    check("edge login->home", any(e["from"] == "loginFragment" and e["to"] == "homeFragment" for e in d["edges"]))
    check("edge has trigger", any(e["trigger"] == "action_login_to_home" for e in d["edges"]))
    for k in ["root","framework","nodes","edges"]:
        check(f"key present: {k}", k in d)
    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 plugins/clone-app/tests/test-extract-nav-graph.py`
Expected: FAIL — script does not exist yet.

- [ ] **Step 4: Write the script**

`plugins/clone-app/skills/clone-app/scripts/extract-nav-graph.py`:
```python
#!/usr/bin/env python3
"""Build a navigation graph from a decompiled APK.

Primary source: res/**/navigation/*.xml (Jetpack Navigation) — fragment/activity/
dialog nodes, <action app:destination> edges. Secondary: Compose NavHost
composable() routes + navigate() calls grepped from .kt sources. Stdlib-only.
Emits nav-graph.json on stdout (or --out FILE).
"""
import os, re, json, glob, argparse
import xml.etree.ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"
APP = "{http://schemas.android.com/apk/res-auto}"

def _clean(s):
    return (s or "").replace("@+id/", "").replace("@id/", "")

def _nav_xml(root):
    nodes, edges = [], []
    for f in glob.glob(os.path.join(root, "**", "navigation", "*.xml"), recursive=True):
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            continue
        rel = os.path.relpath(f, root)
        for el in tree.getroot().iter():
            tag = el.tag.split("}")[-1]
            if tag not in ("fragment", "activity", "dialog"):
                continue
            nid = _clean(el.get(ANDROID + "id"))
            if not nid:
                continue
            nodes.append({"id": nid, "label": el.get(ANDROID + "name", ""),
                          "kind": tag, "source": rel})
            for child in list(el):
                if child.tag.split("}")[-1] == "action":
                    dest = _clean(child.get(APP + "destination"))
                    if dest:
                        edges.append({"from": nid, "to": dest,
                                      "trigger": _clean(child.get(ANDROID + "id")),
                                      "source": rel})
    return nodes, edges

def _compose(root):
    nodes, edges = [], []
    comp_pat = re.compile(r'composable\(\s*["\']([^"\']+)["\']')
    nav_pat = re.compile(r'navigate\(\s*["\']([^"\']+)["\']')
    for dp, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".kt"):
                continue
            path = os.path.join(dp, fn)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "NavHost" not in text:
                continue
            rel = os.path.relpath(path, root)
            for m in comp_pat.finditer(text):
                nodes.append({"id": m.group(1), "label": m.group(1),
                              "kind": "composable", "source": rel})
            for m in nav_pat.finditer(text):
                edges.append({"from": None, "to": m.group(1),
                              "trigger": "navigate", "source": rel})
    return nodes, edges

def extract(root):
    n1, e1 = _nav_xml(root)
    n2, e2 = _compose(root)
    fw = "navigation-xml" if n1 else ("compose" if n2 else "unknown")
    return {"root": root, "framework": fw, "nodes": n1 + n2, "edges": e1 + e2}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="decompile output root")
    ap.add_argument("--out")
    args = ap.parse_args()
    text = json.dumps(extract(args.root), indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 plugins/clone-app/tests/test-extract-nav-graph.py`
Expected: PASS on every line; exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/skills/clone-app/scripts/extract-nav-graph.py \
        plugins/clone-app/tests/test-extract-nav-graph.py \
        plugins/clone-app/tests/fixtures/nav-sample/
git commit -m "feat(clone-app): extract-nav-graph.py — navigation graph from nav XML + Compose"
```

---

### Task 3: New reference rubrics (fidelity pass, logic capture, backend recon)

**Files:**
- Create: `plugins/clone-app/skills/clone-app/references/fidelity-pass-guide.md`
- Create: `plugins/clone-app/skills/clone-app/references/logic-capture-guide.md`
- Create: `plugins/clone-app/skills/clone-app/references/backend-recon-guide.md`
- Modify: `plugins/clone-app/tests/test-references-content.sh`

**Interfaces:**
- Consumes: the artifact names produced by Tasks 1–2 (`logic-digest.md` ← `extract-logic.py`, `nav-graph.json` ← `extract-nav-graph.py`).
- Produces: three reference docs the Phase 8 subagent (Task 7) reads; grep anchors `fidelity-report`, `logic-digest.md`, `nav-graph.json`, `backend-recon.md`, `confidence` for tests.

- [ ] **Step 1: Write `fidelity-pass-guide.md`**

`plugins/clone-app/skills/clone-app/references/fidelity-pass-guide.md`:
```markdown
# Fidelity Pass Guide

The fidelity pass is the deep-extraction step that runs **only when the user
proceeds to build a plan at the Phase 7 gate**. There is no mode flag. Phases
0–6 already produced the feasibility report (`clone-report-<date>.md`); the
fidelity pass adds a second standalone report (`fidelity-report-<date>.md`) and
the build spec. The generated implementation plan references **both** reports.

## What it reuses

The fidelity pass does NOT re-download or re-decompile. It reads what Phase 2
already wrote to `$WORK/output` (sources, resources). It runs inside a Phase 8
subagent so deep extraction never floods the orchestrator context.

## Steps (Phase 8 subagent)

1. **Full Tier-2 payloads.** Extend `$WORK/payloads.json` so EVERY first-party
   endpoint carries request/response/headers — not just auth/payment/core.
   Third-party endpoints stay Tier-1. This overrides the token-cost non-goal in
   `re-digest-contract.md`, which governs only the Phase 2 feasibility pass.
2. **In-app logic.** Run `extract-logic.py "$WORK/output" --out "$WORK/logic-signals.json"`,
   then distill `$WORK/logic-digest.md` per `logic-capture-guide.md`.
3. **Navigation graph.** Run `extract-nav-graph.py "$WORK/output" --out "$WORK/nav-graph.json"`.
4. **Backend recon.** Write `$WORK/backend-recon.md` from the contract per
   `backend-recon-guide.md` (confidence-stamped; a rebuild target, not stolen code).
5. **Unity (if applicable).** Deepen `$WORK/unity-digest.md` with game
   mechanics / formulas per `unity-re-guide.md`.

## Outputs

- `$WORK/logic-digest.md`, `$WORK/nav-graph.json`, `$WORK/backend-recon.md`
- deepened `$WORK/payloads.json`
- `$WORK/fidelity-report-<date>.md` (standalone)
- the fidelity build spec (`clone-build-spec-template.md`, fidelity sections)

## Honest limits

Native Kotlin/Java and Unity-mono yield strong logic extraction; Unity-il2cpp is
medium; Flutter/React Native fall back to a `limited:` digest (Dart/JS are not in
the Java decompile). Backend server logic is never in the APK — `backend-recon.md`
infers a design, it does not recover server code.
```

- [ ] **Step 2: Write `logic-capture-guide.md`**

`plugins/clone-app/skills/clone-app/references/logic-capture-guide.md`:
```markdown
# Logic Capture Guide

How the Phase 8 subagent turns `extract-logic.py`'s JSON signals (plus the
sources under `$WORK/output`) into `$WORK/logic-digest.md`.

## Input

`extract-logic.py "$WORK/output" --out "$WORK/logic-signals.json"` emits an
inventory: `viewmodels`, `usecases`, `validation`, `state_enums`,
`room_entities`, `room_daos`. Use it as the index of where logic lives; open the
named files to read the actual rules.

## `logic-digest.md` sections

```
# Logic Digest — <pkg>
## Workflows        per user flow (onboarding, core loop, payment): the step
                    sequence, the screen at each step, the trigger to advance
## Business rules   validation rules, computed values, formulas (from the
                    ViewModels / use-cases the signals point at)
## State model      state_enums + sealed classes → the states and transitions
## Local data       Room entities + DAOs → tables, columns, queries
## Confidence       per framework (see below)
```

## Framework-aware confidence

| Framework | Logic recoverable? | Confidence |
|---|---|---|
| Native Kotlin/Java (post R8 name recovery) | ViewModels, use-cases, validation read well | high |
| Jetpack Compose | logic in Kotlin, readable | high |
| Unity (mono) | C# near-source — mechanics + formulas | high–med |
| Unity (il2cpp) | type model + partial method bodies | med |
| Flutter / React Native | Dart/JS not in Java decompile | low — say so |

When confidence is low, record what little is recoverable (manifest, strings,
SDK list) and lean on screenshots + the API contract.
```

- [ ] **Step 3: Write `backend-recon-guide.md`**

`plugins/clone-app/skills/clone-app/references/backend-recon-guide.md`:
```markdown
# Backend Recon Guide

The APK is the client. Server-side code is NOT in it. `backend-recon.md` INFERS a
backend design from the observed API contract so a fresh session can REBUILD the
backend — it is a design target, not recovered server code. Every inference is
confidence-stamped.

## Input

`$WORK/payloads.json` (deepened to full Tier-2 in the fidelity pass) +
`$WORK/re-digest.md` (hosts, auth model, BuildConfig).

## `backend-recon.md` sections

```
# Backend Recon — <pkg>
## Entities         from request/response bodies: each object → table + fields +
                    inferred types; mark which are observed vs guessed
## Relationships    foreign keys / nesting inferred from payload shapes
## Endpoints        per endpoint: method, path, auth, what it reads/writes,
                    inferred server-side validation and side effects
## Auth model       token type, header, refresh flow (from auth payloads)
## Confidence       high = directly observed in payloads; med = inferred from
                    naming/shape; low = guessed, needs runtime confirmation
```

## Rules

- Never present an inference as fact. Tag every entity/rule high/med/low.
- Prefer "observed in `POST /v1/auth/login` response" citations over assertions.
- Where the contract is silent (e.g. server-only business rules), say
  "not observable statically — confirm via dynamic analysis (Phase B)".
```

- [ ] **Step 4: Add grep assertions to `test-references-content.sh`**

In `plugins/clone-app/tests/test-references-content.sh`, before the final `exit $fail`, add:
```bash
has "$R/fidelity-pass-guide.md" "fidelity-report"
has "$R/fidelity-pass-guide.md" "logic-digest.md"
has "$R/fidelity-pass-guide.md" "nav-graph.json"
has "$R/fidelity-pass-guide.md" "backend-recon.md"
has "$R/logic-capture-guide.md" "extract-logic.py"
has "$R/logic-capture-guide.md" "confidence"
has "$R/backend-recon-guide.md" "rebuild"
has "$R/backend-recon-guide.md" "confidence"
```

- [ ] **Step 5: Run the references test**

Run: `bash plugins/clone-app/tests/test-references-content.sh`
Expected: every line PASS (including the existing checks and the 8 new ones); exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/skills/clone-app/references/fidelity-pass-guide.md \
        plugins/clone-app/skills/clone-app/references/logic-capture-guide.md \
        plugins/clone-app/skills/clone-app/references/backend-recon-guide.md \
        plugins/clone-app/tests/test-references-content.sh
git commit -m "docs(clone-app): fidelity-pass, logic-capture, backend-recon rubrics"
```

---

### Task 4: Document fidelity artifacts in `re-digest-contract.md`

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/references/re-digest-contract.md` (append a new section at end of file)
- Modify: `plugins/clone-app/tests/test-references-content.sh`

**Interfaces:**
- Consumes: artifact names + schemas from Tasks 1–2.
- Produces: the documented contract for `logic-digest.md`, `nav-graph.json`, `backend-recon.md` + the Tier-2-on-all rule; grep anchors `logic-digest.md`, `nav-graph.json`, `backend-recon.md`.

- [ ] **Step 1: Append the fidelity-pass section**

Append to the end of `plugins/clone-app/skills/clone-app/references/re-digest-contract.md`:
```markdown

## Fidelity pass artifacts (Phase 8 — proceed-to-build only)

When the user proceeds to build at the Phase 7 gate, the Phase 8 fidelity
subagent reuses `$WORK/output` (no re-decompile) and ALSO writes:

- `$WORK/logic-digest.md` — in-app logic & workflows, distilled from
  `extract-logic.py`'s signals per `logic-capture-guide.md`.
- `$WORK/nav-graph.json` — navigation graph from `extract-nav-graph.py`
  (keys: `root`, `framework`, `nodes[]`, `edges[]`).
- `$WORK/backend-recon.md` — inferred backend design per `backend-recon-guide.md`
  (confidence-stamped; a rebuild target, not recovered server code).

It also **deepens `$WORK/payloads.json`**: in the fidelity pass, Tier-2
request/response/headers are populated for **every first-party endpoint**, not
just auth/payment/core. This overrides the "Tier-2 on every endpoint is a
non-goal" rule above, which governs ONLY the Phase 2 feasibility pass.
```

- [ ] **Step 2: Add grep assertions to `test-references-content.sh`**

Add before the final `exit $fail`:
```bash
has "$R/re-digest-contract.md" "logic-digest.md"
has "$R/re-digest-contract.md" "nav-graph.json"
has "$R/re-digest-contract.md" "backend-recon.md"
```

- [ ] **Step 3: Run the references test**

Run: `bash plugins/clone-app/tests/test-references-content.sh`
Expected: all PASS; exit 0.

- [ ] **Step 4: Commit**

```bash
git add plugins/clone-app/skills/clone-app/references/re-digest-contract.md \
        plugins/clone-app/tests/test-references-content.sh
git commit -m "docs(clone-app): contract for fidelity-pass artifacts in re-digest-contract"
```

---

### Task 5: Deepen `clone-build-spec-template.md` (fidelity sections)

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/references/clone-build-spec-template.md`
- Modify: `plugins/clone-app/tests/test-references-content.sh`

**Interfaces:**
- Consumes: `logic-digest.md`, `nav-graph.json`, `backend-recon.md` (Tasks 1–4).
- Produces: build-spec sections §3b and §5b + deepened §3/§4/§6; grep anchors `User-flow diagrams`, `Backend rebuild spec`.

- [ ] **Step 1: Edit §3, §4, §6 and insert §3b, §5b**

In `plugins/clone-app/skills/clone-app/references/clone-build-spec-template.md`, replace the §3 and §4 blocks:

Replace:
```markdown
## 3. Screen-by-screen spec
For **each** screen: purpose · layout · components · states (empty/loading/error)
· navigation in/out · matching screenshot (`$WORK/screenshots/NN.png`).

## 4. Navigation map / IA
The full screen graph + entry points.
```
with:
```markdown
## 3. Screen-by-screen spec
For **each** screen: purpose · layout **component tree** (from native XML) ·
components · states (empty/loading/error) · navigation in/out · the screen's
logic (cross-ref `$WORK/logic-digest.md`) · matching screenshot
(`$WORK/screenshots/NN.png`).

## 3b. User-flow diagrams
Step-by-step flows (onboarding, core loop, payment) from `$WORK/logic-digest.md`:
each step's screen, the action that advances it, and the API call it triggers.

## 4. Navigation map / IA
The full screen graph + entry points, generated from `$WORK/nav-graph.json`
(nodes = screens, edges = transitions + triggers) — not inferred.
```

Then, immediately after the §5 API contract block, insert:
```markdown
## 5b. Backend rebuild spec
The from-scratch backend design from `$WORK/backend-recon.md`: per-endpoint
behavior, auth flow, inferred server-side validation. Confidence-stamped — this
is a rebuild target, not recovered server code.
```

And replace the §6 block:
```markdown
## 6. Data model
Entities, fields, relationships (from payloads + RE digest).
```
with:
```markdown
## 6. Data model
Entities, fields, relationships from `$WORK/backend-recon.md` (observed vs
inferred, each confidence-stamped).
```

- [ ] **Step 2: Add grep assertions to `test-references-content.sh`**

Add before the final `exit $fail`:
```bash
has "$R/clone-build-spec-template.md" "User-flow diagrams"
has "$R/clone-build-spec-template.md" "Backend rebuild spec"
has "$R/clone-build-spec-template.md" "nav-graph.json"
has "$R/clone-build-spec-template.md" "logic-digest.md"
```

- [ ] **Step 3: Run the references test**

Run: `bash plugins/clone-app/tests/test-references-content.sh`
Expected: all PASS (existing `Screen-by-screen`, `Acceptance criteria`, `Game variant` still match); exit 0.

- [ ] **Step 4: Commit**

```bash
git add plugins/clone-app/skills/clone-app/references/clone-build-spec-template.md \
        plugins/clone-app/tests/test-references-content.sh
git commit -m "docs(clone-app): fidelity sections in clone-build-spec template"
```

---

### Task 6: Deepen `unity-re-guide.md` (game mechanics / formulas)

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/references/unity-re-guide.md` (append a section)
- Modify: `plugins/clone-app/tests/test-references-content.sh`

**Interfaces:**
- Consumes: existing Unity RE outputs (`unity-digest.md`).
- Produces: documented game-mechanic extraction depth; grep anchor `game mechanics`.

- [ ] **Step 1: Append the game-mechanics section**

Append to the end of `plugins/clone-app/skills/clone-app/references/unity-re-guide.md`:
```markdown

## Game mechanics & formulas (fidelity pass)

In the Phase 8 fidelity pass, deepen `$WORK/unity-digest.md` beyond the type
model + netcode to capture the playable rules:

- **Game mechanics** — core loop, win/lose conditions, level/wave progression,
  player/enemy state machines (from the C# `MonoBehaviour` methods).
- **Formulas** — damage/score/economy/cooldown calculations, drop rates, curve
  tables (constants and arithmetic in the decompiled C#).
- **Tunables** — `ScriptableObject` configs and serialized fields that balance
  the game.

Confidence: Unity **mono** is near-source (high); **il2cpp** gives signatures +
partial bodies (med). State the level reached.
```

- [ ] **Step 2: Add grep assertion to `test-references-content.sh`**

Add before the final `exit $fail`:
```bash
has "$R/unity-re-guide.md" "game mechanics"
```

- [ ] **Step 3: Run the references test**

Run: `bash plugins/clone-app/tests/test-references-content.sh`
Expected: all PASS (existing `Il2CppInspectorRedux`, `AssetRipper`, `ilspycmd` still match); exit 0.

- [ ] **Step 4: Commit**

```bash
git add plugins/clone-app/skills/clone-app/references/unity-re-guide.md \
        plugins/clone-app/tests/test-references-content.sh
git commit -m "docs(clone-app): game-mechanics extraction depth in unity-re-guide"
```

---

### Task 7: Wire the fidelity pass into `SKILL.md` (Phase 7 trigger + Phase 8)

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/SKILL.md`
- Modify: `plugins/clone-app/tests/test-skill-phases.sh`

**Interfaces:**
- Consumes: every artifact and rubric from Tasks 1–6 (`extract-logic.py`, `extract-nav-graph.py`, `logic-digest.md`, `nav-graph.json`, `backend-recon.md`, `fidelity-pass-guide.md`, `backend-recon-guide.md`, `logic-capture-guide.md`).
- Produces: the orchestrator prose that triggers the fidelity pass and emits two reports; grep anchors for `test-skill-phases.sh`.

- [ ] **Step 1: Rewrite Phase 7 to trigger the fidelity pass**

In `plugins/clone-app/skills/clone-app/SKILL.md`, replace the Phase 7 block:
```markdown
## Phase 7: Decision Gate

Ask: "Report saved to `$WORK/clone-report-<date>.md`. Proceed to build the
implementation plan?"
- **Yes** → proceed to Phase 8 to assemble the clone build spec, then hand off
  to `superpowers:writing-plans`.
- **No** → stop; the report stands on its own.
```
with:
```markdown
## Phase 7: Decision Gate

Ask: "Feasibility report saved to `$WORK/clone-report-<date>.md`. Proceed to
build the implementation plan? (This runs the deep **fidelity pass** — full
API payloads, in-app logic, navigation graph, and an inferred backend design —
and produces a second report.)"
- **Yes** → run Phase 8: the fidelity pass, then assemble the build spec and
  hand off to `superpowers:writing-plans`.
- **No** → stop; the feasibility report stands on its own. The fidelity pass
  (and its token cost) is never incurred.
```

- [ ] **Step 2: Rewrite Phase 8 to run the fidelity pass before assembling the spec**

Replace the Phase 8 block (from `## Phase 8: Assemble the Clone Build Spec` through the end of that section, up to but not including `## Error Handling Summary`) with:
```markdown
## Phase 8: Fidelity Pass + Build Spec

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/fidelity-pass-guide.md`.

### Phase 8a — Fidelity subagent (deep extraction)

Dispatch one subagent (Agent tool, `general-purpose`). It reuses what Phase 2
already decompiled to `$WORK/output` — **no re-download, no re-decompile**. Pass
it `$PKG`, `$WORK`, the clone-app scripts dir `$CA`
(`${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/`), and the paths to
`fidelity-pass-guide.md`, `logic-capture-guide.md`, `backend-recon-guide.md`.
Its instructions:

1. **Full Tier-2 payloads.** Extend `$WORK/payloads.json` so every first-party
   endpoint carries request/response/headers (third-party stays Tier-1).
2. **In-app logic.** Run
   `python3 "$CA/extract-logic.py" "$WORK/output" --out "$WORK/logic-signals.json"`,
   then write `$WORK/logic-digest.md` per `logic-capture-guide.md`.
3. **Navigation graph.** Run
   `python3 "$CA/extract-nav-graph.py" "$WORK/output" --out "$WORK/nav-graph.json"`.
4. **Backend recon.** Write `$WORK/backend-recon.md` per `backend-recon-guide.md`.
5. **Unity (if RE Method indicated Unity).** Deepen `$WORK/unity-digest.md` with
   game mechanics / formulas per `unity-re-guide.md`.
6. **Return** a short fidelity summary + the artifact paths — never raw sources.

If the subagent fails, retry once; if it still fails, continue with whatever
artifacts exist and note the gap in the fidelity report.

### Phase 8b — Fidelity report

Write `$WORK/fidelity-report-<YYYY-MM-DD>.md` (actual run date): summarize the
logic digest, navigation graph, full API surface, and backend recon, each with
its confidence. This is a standalone report alongside the feasibility one.

### Phase 8c — Build spec

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/clone-build-spec-template.md`.
Assemble `$WORK/clone-build-spec.md`, filling every section from the artifacts:
- §2 from `$WORK/design-tokens.json` (+ `design-digest.md`),
- §3 one entry per screen, each paired with `$WORK/screenshots/NN.png`, plus its
  logic from `$WORK/logic-digest.md`,
- §3b user-flow diagrams from `$WORK/logic-digest.md`,
- §4 from `$WORK/nav-graph.json`,
- §5 from `$WORK/payloads.json` (full Tier-2), §5b + §6 from `$WORK/backend-recon.md`,
- §7 asset inventory from `$WORK/output` (or `$WORK/game-assets/` for Unity),
- §8 acceptance criteria per screen + flow,
- §10 absolute paths to every `$WORK/` artifact.
Use the **Game variant** sections when RE Method indicated Unity.

Then invoke `superpowers:writing-plans`, passing `$WORK/clone-build-spec.md` as
the spec and citing BOTH `$WORK/clone-report-<date>.md` and
`$WORK/fidelity-report-<date>.md` as reference. The build spec + `$WORK/` is the
standalone input — a fresh session with it can build an exact / near-exact clone.
```

- [ ] **Step 3: Add fidelity rows to the Error Handling Summary table**

In the `## Error Handling Summary` table in `SKILL.md`, add these rows before the closing of the table:
```markdown
| Phase 7 = No | stop after feasibility report; skip the fidelity pass |
| Fidelity subagent fails | retry once, then continue with partial artifacts and note the gap |
| extract-logic/nav-graph finds nothing (Flutter/RN) | note low confidence, lean on screenshots + API contract |
```

- [ ] **Step 4: Add grep assertions to `test-skill-phases.sh`**

In `plugins/clone-app/tests/test-skill-phases.sh`, add before `exit $fail`:
```bash
has "extract-logic.py"
has "extract-nav-graph.py"
has "logic-digest.md"
has "nav-graph.json"
has "backend-recon.md"
has "fidelity-report-"
has "fidelity-pass-guide.md"
```

- [ ] **Step 5: Run the skill-phases test**

Run: `bash plugins/clone-app/tests/test-skill-phases.sh`
Expected: all PASS (existing anchors `extract-design.py`, `## Phase 8`, `clone-build-spec.md` etc. still match); exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/skills/clone-app/SKILL.md \
        plugins/clone-app/tests/test-skill-phases.sh
git commit -m "feat(clone-app): wire Phase 7 trigger + Phase 8 fidelity pass into SKILL"
```

---

### Task 8: Register new scripts/references in smoke structure + full-suite green

**Files:**
- Modify: `plugins/clone-app/tests/smoke-structure.sh`

**Interfaces:**
- Consumes: all files created in Tasks 1–7.
- Produces: structural guarantee that the new scripts/references exist; final green suite.

- [ ] **Step 1: Add new scripts to the smoke structure check**

In `plugins/clone-app/tests/smoke-structure.sh`, change the python-scripts loop:
```bash
for s in scrape-play-store.py check-appstore.py extract-design.py; do
  must_exist "$P/skills/clone-app/scripts/$s"
done
```
to:
```bash
for s in scrape-play-store.py check-appstore.py extract-design.py extract-logic.py extract-nav-graph.py; do
  must_exist "$P/skills/clone-app/scripts/$s"
done
```

- [ ] **Step 2: Add new references to the smoke structure check**

In the same file, change the references loop:
```bash
for r in stack-recommendation-guide effort-estimation-guide infra-cost-guide report-template re-digest-contract design-capture-guide unity-re-guide clone-build-spec-template; do
  must_exist "$P/skills/clone-app/references/$r.md"
done
```
to:
```bash
for r in stack-recommendation-guide effort-estimation-guide infra-cost-guide report-template re-digest-contract design-capture-guide unity-re-guide clone-build-spec-template fidelity-pass-guide logic-capture-guide backend-recon-guide; do
  must_exist "$P/skills/clone-app/references/$r.md"
done
```

- [ ] **Step 3: Run the smoke structure test**

Run: `bash plugins/clone-app/tests/smoke-structure.sh`
Expected: all PASS including the 5 scripts and 11 references; exit 0.

- [ ] **Step 4: Run the full suite**

Run: `bash plugins/clone-app/tests/run-all.sh`
Expected: final line `ALL TESTS PASSED`; exit 0. (Confirms `test-extract-logic.py` and `test-extract-nav-graph.py` were auto-picked up by the globs.)

- [ ] **Step 5: Verify the upstream tree is untouched**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: no output (empty).

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/tests/smoke-structure.sh
git commit -m "test(clone-app): register fidelity scripts + rubrics in smoke structure"
```

---

## Self-Review

**Spec coverage** (against `2026-06-25-clone-app-fidelity-pass-design.md`):
- §4.1 two reports, no flag, Phase 7 trigger → Task 7 (Phase 7/8 rewrite, `fidelity-report-<date>.md`). ✓
- §4.2 `payloads.json` deepened → Task 7 step 2.1; `logic-digest.md` → Tasks 1+7; `nav-graph.json` → Tasks 2+7; `backend-recon.md` → Tasks 3+7; `unity-digest.md` deepened → Task 6. ✓
- §4.3 build-spec fidelity variant (§3, §3b, §4, §5, §5b, §6, game variant) → Task 5. ✓
- §5.1 new scripts → Tasks 1, 2. ✓
- §5.2 new references → Task 3. ✓
- §5.3 changed files (`SKILL.md`, `re-digest-contract.md`, `clone-build-spec-template.md`, `unity-re-guide.md`) → Tasks 7, 4, 5, 6. ✓
- §5.4 untouched (`extract-design.py`, RE tree, feasibility path) → no task modifies them; constraint enforced in Task 8 step 5. ✓
- §6 testing (`test-extract-logic.py`, `test-extract-nav-graph.py`, smoke + skill-content updates, run-all auto-register) → Tasks 1, 2, 7, 8. ✓

**Placeholder scan:** No TBD/TODO; every script and doc step contains full content; every test step shows the command + expected result. ✓

**Type consistency:** `extract-logic.py` JSON keys (`viewmodels`, `usecases`, `validation`, `state_enums`, `room_entities`, `room_daos`) match between Task 1 script, Task 1 test, and the `logic-capture-guide.md` input description (Task 3). `extract-nav-graph.py` keys (`root`, `framework`, `nodes`, `edges`) match between Task 2 script, Task 2 test, and `re-digest-contract.md` (Task 4). Artifact filenames (`logic-digest.md`, `nav-graph.json`, `backend-recon.md`, `fidelity-report-<date>.md`) are spelled identically across Tasks 3–7 and the grep assertions. ✓
