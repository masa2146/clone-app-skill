# Clone App — RE-via-Subagent + Payload Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite clone-app Phase 2 to run the `android-reverse-engineering` skill inside an isolated subagent (falling back to direct scripts), extract Tier-2 payloads for auth/payment/core flows, and persist a durable digest contract to `$WORK/`.

**Architecture:** Phase 2 becomes probe → dispatch → consume. A dispatched subagent runs RE in its own context and writes three files (`re-digest.md`, `payloads.json`, `re-summary.txt`) to `$WORK/`; the orchestrator ingests only the ≤40-line summary. A new reference doc `re-digest-contract.md` is the single source of truth for the schema. Both the skill branch and the script-fallback branch write the same files, so Phases 3–7 stay branch-agnostic. The work product is Markdown (SKILL.md prose + reference doc) plus structural bash tests — there is no compiled runtime, so "tests" assert document structure and wiring, matching the repo's existing offline test philosophy.

**Tech Stack:** Bash (`#!/usr/bin/env bash`, invoked via `bash <path>`), Python 3 stdlib (`json` for validity checks), Markdown skill/reference docs.

## Global Constraints

- **Upstream untouched:** No edits under `plugins/android-reverse-engineering/`. After every commit, `git status --porcelain plugins/android-reverse-engineering/` MUST print nothing.
- **All new/changed files live under `plugins/clone-app/`** (plus the design docs already committed).
- **Bash scripts use `#!/usr/bin/env bash`** and are run with `bash <path>` (shell is zsh; `sh` breaks them). Tests use `set -uo pipefail` (NOT `-e`) and aggregate failures into a `fail` var so every assertion runs.
- **Python is stdlib-only** — `json`, no pip, no venv.
- **Effort is measured in "AI Sprints"** (one focused Claude session), never calendar time — preserve this wording in any SKILL.md edits.
- **Conventional Commits scoped to the plugin:** `feat(clone-app): …`, `test(clone-app): …`, `docs(clone-app): …`.
- **Two pause points in SKILL.md stay:** Phase 4 (choose stack) and Phase 7 (proceed to plan?). Do not add new mandatory pauses in Phase 2.
- **Working dir convention:** `WORK="./work/$PKG"` relative to the user's cwd; decompile output lands at `$WORK/output/` via `decompile.sh -o`.

---

### Task 1: Digest contract reference doc + schema fixtures + contract test

Establishes the single source of truth for what the subagent must produce, plus offline fixtures and a structural test that locks the schema. This task is independently reviewable: a reviewer can accept the contract/fixtures/test without yet seeing the SKILL.md rewrite.

**Files:**
- Create: `plugins/clone-app/skills/clone-app/references/re-digest-contract.md`
- Create: `plugins/clone-app/tests/fixtures/re-digest.sample.md`
- Create: `plugins/clone-app/tests/fixtures/payloads.sample.json`
- Test: `plugins/clone-app/tests/test-re-digest-contract.sh`

**Interfaces:**
- Produces (consumed by Task 2's SKILL.md prose and by the subagent at runtime):
  - `re-digest.md` required section headings (exact strings): `## Framework & Stack`, `## Hosts`, `## Endpoint Inventory`, `## Key Flow Payloads`, `## BuildConfig Secrets`, `## Feature Signals`, `## RE Method`.
  - `payloads.json` required top-level keys: `package`, `re_method`, `endpoints`, `buildconfig`. Each `endpoints[]` object has keys: `host`, `method`, `path`, `auth`, `source`, `request_body`, `response`, `headers`.
  - `re-summary.txt`: plain text, ≤40 lines, fields — framework, host count, endpoint count, key-flow names, secrets-found count, RE method, blockers.
  - `RE Method` allowed values: `re-skill`, `direct-scripts`, `limited: <framework>`.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-re-digest-contract.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="$HERE/.."   # plugins/clone-app
CONTRACT="$P/skills/clone-app/references/re-digest-contract.md"
DIGEST_FIX="$HERE/fixtures/re-digest.sample.md"
PAYLOAD_FIX="$HERE/fixtures/payloads.sample.json"
fail=0
has() { grep -qF "$2" "$1" && echo "PASS: $3" || { echo "FAIL: $3 — '$2' not in ${1##*/}"; fail=1; }; }

# Contract doc exists and documents every required re-digest.md section heading
for sec in "## Framework & Stack" "## Hosts" "## Endpoint Inventory" \
           "## Key Flow Payloads" "## BuildConfig Secrets" "## Feature Signals" "## RE Method"; do
  has "$CONTRACT" "$sec" "contract documents section $sec"
done

# Contract doc documents every required payloads.json key
for key in '"package"' '"re_method"' '"endpoints"' '"buildconfig"' \
           '"request_body"' '"response"' '"headers"'; do
  has "$CONTRACT" "$key" "contract documents json key $key"
done

# Contract names the three output files and the three RE Method values
for tok in "re-digest.md" "payloads.json" "re-summary.txt" \
           "re-skill" "direct-scripts" "limited:"; do
  has "$CONTRACT" "$tok" "contract names token $tok"
done

# Digest fixture has every required section heading
for sec in "## Framework & Stack" "## Hosts" "## Endpoint Inventory" \
           "## Key Flow Payloads" "## BuildConfig Secrets" "## Feature Signals" "## RE Method"; do
  has "$DIGEST_FIX" "$sec" "digest fixture has section $sec"
done

# Payload fixture is valid JSON and has the required shape
python3 -c "
import json,sys
d=json.load(open('$PAYLOAD_FIX'))
for k in ('package','re_method','endpoints','buildconfig'):
    assert k in d, 'missing top key '+k
assert isinstance(d['endpoints'],list) and d['endpoints'], 'endpoints must be non-empty list'
for e in d['endpoints']:
    for k in ('host','method','path','auth','source','request_body','response','headers'):
        assert k in e, 'endpoint missing key '+k
print('PASS: payload fixture shape valid')
" || { echo "FAIL: payload fixture shape"; fail=1; }

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-re-digest-contract.sh`
Expected: FAIL — contract doc and fixtures do not exist yet (grep errors / `FAIL:` lines), exit non-zero.

- [ ] **Step 3: Create the contract reference doc**

Create `plugins/clone-app/skills/clone-app/references/re-digest-contract.md`:

````markdown
# RE Digest Contract

The Phase 2 subagent runs the reverse-engineering workflow in isolation and
MUST produce these three files under `$WORK/`, then return only the summary.
This file is the single source of truth for their schema. The subagent prompt
points here; do not duplicate the schema into SKILL.md prose.

## File 1 — `$WORK/re-digest.md` (human-readable, main artifact)

Required section headings, in this order:

```
# RE Digest — <pkg>
## Framework & Stack    framework, HTTP lib, DI, serialization, obfuscation level
## Hosts                first-party vs third-party (table)
## Endpoint Inventory   Tier-1: host | method | path | auth | source file
## Key Flow Payloads    Tier-2: auth, payment/checkout, 1-2 core flows
                        — request body / response shape / headers / params
## BuildConfig Secrets  base URLs, API keys, feature flags, flavors
## Feature Signals      screen count, SDKs, permissions, components
## RE Method            re-skill | direct-scripts | limited: <framework>
```

## File 2 — `$WORK/payloads.json` (machine-readable, durable memory)

Required top-level keys: `package`, `re_method`, `endpoints`, `buildconfig`.
Each item in `endpoints` has: `host`, `method`, `path`, `auth`, `source`,
`request_body`, `response`, `headers`.

```json
{
  "package": "com.example.app",
  "re_method": "re-skill",
  "endpoints": [
    {
      "host": "api.example.com",
      "method": "POST",
      "path": "/v1/auth/login",
      "auth": "none",
      "source": "com/example/api/AuthApi.java",
      "request_body": { "email": "string", "password": "string" },
      "response": { "token": "string", "user": {} },
      "headers": { "Content-Type": "application/json" }
    }
  ],
  "buildconfig": { "BASE_URL": "https://api.example.com/v1" }
}
```

- `request_body` and `response` are `null` for Tier-1-only endpoints.
- Populate them ONLY for the key flows: **auth, payment/checkout, and the
  1–2 core feature endpoints** (decision Q3=B). Everything else is a Tier-1
  row with `null` payloads. Going Tier-2 on every endpoint is a non-goal —
  it is token-expensive and the RE skill itself warns against it.

## File 3 — `$WORK/re-summary.txt` (≤40 lines, the only RE text returned)

Plain text. The subagent's return value = the contents of this file plus the
paths to the two files above. Fields:

- framework
- host count (first-party / third-party)
- endpoint count
- key-flow names found (auth / payment / core)
- secrets-found count (BuildConfig)
- RE method: `re-skill` | `direct-scripts` | `limited: <framework>`
- blockers / warnings (e.g. obfuscation, framework guard)

The subagent MUST NOT return raw decompiled sources.

## RE Method values

| Value | Meaning |
|---|---|
| `re-skill` | The `android-reverse-engineering` skill ran the workflow. |
| `direct-scripts` | The skill was absent; the sibling plugin's bash scripts ran. |
| `limited: <framework>` | Flutter / React Native / Cordova / Xamarin — Java decompile is shallow; payloads may be empty and the digest is partial. |

## Framework guard

If the fingerprint reports Flutter / React Native / Cordova / Xamarin, set
`RE Method: limited: <framework>`, write whatever partial signals are
available (manifest, strings, hardcoded URLs, SDK list), and leave payloads
empty where they cannot be recovered. Downstream phases widen the
uncertainty band accordingly.
````

- [ ] **Step 4: Create the digest fixture**

Create `plugins/clone-app/tests/fixtures/re-digest.sample.md`:

```markdown
# RE Digest — com.example.app

## Framework & Stack
Native Kotlin · Retrofit + OkHttp · Hilt · kotlinx.serialization · obfuscation: moderate

## Hosts
| Host | Party |
|------|-------|
| api.example.com | first |
| analytics.thirdparty.io | third |

## Endpoint Inventory
| Host | Method | Path | Auth | Source |
|------|--------|------|------|--------|
| api.example.com | POST | /v1/auth/login | none | com/example/api/AuthApi.java |
| api.example.com | GET | /v1/users/profile | Bearer | com/example/api/UserApi.java |
| api.example.com | POST | /v1/orders | Bearer | com/example/api/OrderApi.java |

## Key Flow Payloads
### POST /v1/auth/login (auth)
- request body: `{ "email": "string", "password": "string" }`
- response: `{ "token": "string", "user": {} }`
- headers: `Content-Type: application/json`

### POST /v1/orders (payment/core)
- request body: `{ "items": [], "total": "number" }`
- response: `{ "order_id": "string", "status": "string" }`
- headers: `Authorization: Bearer <token>`

## BuildConfig Secrets
- BASE_URL = https://api.example.com/v1
- ANALYTICS_KEY = <redacted-present>

## Feature Signals
~18 screens · SDKs: Firebase, AppsFlyer · permissions: INTERNET, ACCESS_NETWORK_STATE

## RE Method
re-skill
```

- [ ] **Step 5: Create the payloads fixture**

Create `plugins/clone-app/tests/fixtures/payloads.sample.json`:

```json
{
  "package": "com.example.app",
  "re_method": "re-skill",
  "endpoints": [
    {
      "host": "api.example.com",
      "method": "POST",
      "path": "/v1/auth/login",
      "auth": "none",
      "source": "com/example/api/AuthApi.java",
      "request_body": { "email": "string", "password": "string" },
      "response": { "token": "string", "user": {} },
      "headers": { "Content-Type": "application/json" }
    },
    {
      "host": "api.example.com",
      "method": "GET",
      "path": "/v1/users/profile",
      "auth": "Bearer",
      "source": "com/example/api/UserApi.java",
      "request_body": null,
      "response": null,
      "headers": { "Authorization": "Bearer <token>" }
    }
  ],
  "buildconfig": { "BASE_URL": "https://api.example.com/v1" }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `bash plugins/clone-app/tests/test-re-digest-contract.sh`
Expected: all `PASS:` lines, exit 0.

- [ ] **Step 7: Verify upstream untouched**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add plugins/clone-app/skills/clone-app/references/re-digest-contract.md \
        plugins/clone-app/tests/fixtures/re-digest.sample.md \
        plugins/clone-app/tests/fixtures/payloads.sample.json \
        plugins/clone-app/tests/test-re-digest-contract.sh
git commit -m "test(clone-app): add RE digest contract, fixtures, structural test"
```

---

### Task 2: Rewrite SKILL.md Phase 2 + update Phases 5–6 + error table

Rewrites Phase 2 to probe/dispatch/consume with the subagent and fallback, wires the digest into Phases 5–6, and extends the error table. The contract test from Task 1 is extended here to assert the SKILL.md wiring, so this task is independently testable.

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/SKILL.md` (Phase 2 block lines 43–71; Phase 5 ~93–99; Phase 6 ~101–112; error table ~122–133)
- Modify: `plugins/clone-app/tests/test-re-digest-contract.sh` (append SKILL.md wiring assertions)

**Interfaces:**
- Consumes (from Task 1): the three output filenames (`re-digest.md`, `payloads.json`, `re-summary.txt`), the `references/re-digest-contract.md` path, and the `RE Method` values.
- Produces: Phase 2 prose that any later phase relies on — `$WORK/re-summary.txt` read in Phase 2c, `$WORK/payloads.json` read in Phase 5, `$WORK/re-digest.md` referenced in Phase 6.

- [ ] **Step 1: Append failing wiring assertions to the test**

Add to the end of `plugins/clone-app/tests/test-re-digest-contract.sh`, BEFORE the final `exit $fail` line (replace that final line):

```bash
# --- SKILL.md Phase 2 wiring (Task 2) ---
SKILL="$P/skills/clone-app/SKILL.md"
hasS() { grep -qF "$1" "$SKILL" && echo "PASS: SKILL $2" || { echo "FAIL: SKILL $2 — '$1' missing"; fail=1; }; }
hasReS() { grep -qE "$1" "$SKILL" && echo "PASS: SKILL $2" || { echo "FAIL: SKILL $2 — /$1/ missing"; fail=1; }; }

hasS "re-digest-contract.md" "Phase 2 points at the digest contract"
hasReS "subagent|Agent tool|dispatch" "Phase 2 dispatches a subagent"
hasS "android-reverse-engineering skill" "Phase 2 names the RE skill branch"
hasS "direct-scripts" "Phase 2 names the script-fallback branch"
hasS "re-summary.txt" "Phase 2c consumes the summary"
hasS "payloads.json" "Phase 5 consumes payloads.json"
hasS "Backend API Surface" "Phase 6 adds the Backend API Surface section"
hasS "RE subagent" "error table covers subagent failure"

exit $fail
```

- [ ] **Step 2: Run test to verify the new assertions fail**

Run: `bash plugins/clone-app/tests/test-re-digest-contract.sh`
Expected: Task-1 assertions still PASS; the new `SKILL …` assertions FAIL (SKILL.md not yet rewritten), exit non-zero.

- [ ] **Step 3: Replace the Phase 2 block in SKILL.md**

In `plugins/clone-app/skills/clone-app/SKILL.md`, replace the entire `## Phase 2: Reverse Engineering` section (from the `## Phase 2` heading through the line ending `...Keep this in context for later phases.`) with:

````markdown
## Phase 2: Reverse Engineering (probe → dispatch → consume)

RE runs inside an **isolated subagent** so the decompiled sources never flood
this orchestrator's context. The subagent prefers the
`android-reverse-engineering` **skill** and falls back to that plugin's bash
**scripts**. Either way it writes the same digest files to `$WORK/`, defined
in `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/re-digest-contract.md`.

### Phase 2a — Probe

```bash
RE="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/resolve-re-scripts.sh 2>/tmp/re-err)"; RC=$?
```
- `RC == 0` → the RE **scripts** are on disk (fallback is available). If it
  printed a `WARNING:` about bash version, the scripts need **bash 4+**
  (macOS ships 3.2; `${VAR,,}` fails as "bad substitution") — install one with
  `brew install bash` before the script-fallback branch can succeed.
- Check your own available-skills list for `android-reverse-engineering` →
  is the RE **skill** registered?

Pick the branch:

| RE skill registered | RE scripts on disk (`RC`) | Branch |
|---|---|---|
| yes | any | **re-skill** |
| no | 0 | **direct-scripts** |
| no | 1 | **stop** — show the `/tmp/re-err` resolver error and halt |

### Phase 2b — Dispatch the subagent

Dispatch one subagent (Agent tool, `general-purpose` type — it can both invoke
skills and run bash). Pass it: `$PKG`, `$APK`, `$WORK`, the chosen **branch**,
the resolved `$RE` scripts dir, and the path to `re-digest-contract.md`. Its
instructions:

1. **Run RE per branch.**
   - **re-skill:** invoke the `android-reverse-engineering` skill on `$APK`,
     output dir `$WORK/output` — run its full workflow (fingerprint, deps,
     decompile, Kotlin-name recovery if Kotlin, API extraction incl. Tier-2).
   - **direct-scripts:** run, in order, reading each output before the next:
     `bash "$RE/fingerprint.sh" "$APK"`, `bash "$RE/check-deps.sh"`
     (install required deps via `bash "$RE/install-dep.sh" <dep>`; ask before
     optional vineflower/dex2jar), `bash "$RE/decompile.sh" -o "$WORK/output" "$APK"`
     (add `--deobf` if obfuscation is heavy), `bash "$RE/recover-kotlin-names.sh"
     "$WORK/output/sources" "$WORK/output/names/"` if Kotlin, then
     `bash "$RE/find-api-calls.sh" "$WORK/output/sources"`.
2. **Framework guard:** if the fingerprint is Flutter / React Native / Cordova
   / Xamarin, Java decompile is shallow — produce a partial digest, set
   `RE Method: limited: <framework>`, payloads may be empty.
3. **Extract** the Tier-1 endpoint inventory and Tier-2 payloads for **auth,
   payment/checkout, and the 1–2 core feature endpoints** (not every endpoint).
4. **Write** `$WORK/re-digest.md`, `$WORK/payloads.json`, `$WORK/re-summary.txt`
   exactly per `re-digest-contract.md`.
5. **Return** the contents of `$WORK/re-summary.txt` plus the two file paths —
   **never** raw decompiled sources.

If the subagent fails, retry once; if it still fails and the **direct-scripts**
branch is available, re-dispatch on that branch; otherwise stop and report.

### Phase 2c — Consume

Read `$WORK/re-summary.txt` (the only RE text in this context). From it you have:
framework, HTTP stack, host counts, endpoint count, key-flow names, secrets
count, and the RE method. Read `$WORK/re-digest.md` or `$WORK/payloads.json`
**on demand** when a later phase needs detail. Keep the summary in context for
Phases 3–7.
````

- [ ] **Step 4: Update Phase 5 to read payloads.json**

In `plugins/clone-app/skills/clone-app/SKILL.md`, in `## Phase 5: Effort & Cost Estimation`, replace the line:

```
- the feature list → AI-Sprint effort table (min-max total, uncertainty band),
```

with:

```
- read `$WORK/payloads.json`; the endpoint count and the payload complexity of
  the key flows size the backend work,
- the feature list + backend surface → AI-Sprint effort table (min-max total,
  uncertainty band; widen the band when RE Method is `limited:`),
```

- [ ] **Step 5: Update Phase 6 to add the Backend API Surface section**

In `## Phase 6: Market Viability Report`, after the sentence ending
`...Fill every section from the data gathered.` add:

```
Include a **Backend API Surface** section: summarize the Tier-1 inventory from
`$WORK/re-digest.md` and the key-flow payloads from `$WORK/payloads.json` (host
list, endpoint count, auth model, and the auth/payment/core request+response
shapes). If RE Method was `limited:`, say so and note the reduced confidence.
```

- [ ] **Step 6: Extend the error table**

In `plugins/clone-app/skills/clone-app/SKILL.md`, in the `## Error Handling Summary` table, replace the row:

```
| RE plugin missing | show resolver error, stop |
```

with these rows:

```
| RE skill + scripts both missing | show resolver error, stop |
| RE subagent fails | retry once, then fall back to direct-scripts branch; else stop |
| Subagent returned no digest files | re-dispatch once; if still missing, stop and report |
```

- [ ] **Step 7: Run the contract test to verify it passes**

Run: `bash plugins/clone-app/tests/test-re-digest-contract.sh`
Expected: all `PASS:` (Task 1 + the new SKILL wiring assertions), exit 0.

- [ ] **Step 8: Verify upstream untouched**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: no output.

- [ ] **Step 9: Commit**

```bash
git add plugins/clone-app/skills/clone-app/SKILL.md \
        plugins/clone-app/tests/test-re-digest-contract.sh
git commit -m "feat(clone-app): run RE via isolated subagent with script fallback + payloads"
```

---

### Task 3: Register the contract doc in the smoke test + full suite green

Adds the new reference file to the structural smoke check and confirms the whole suite passes. A reviewer can reject this independently if the smoke test or aggregate run regresses.

**Files:**
- Modify: `plugins/clone-app/tests/smoke-structure.sh:19-21` (the references loop)

**Interfaces:**
- Consumes (from Task 1): the reference filename `re-digest-contract`.
- Produces: nothing downstream — terminal verification task.

- [ ] **Step 1: Add the new reference to the smoke test's existence check**

In `plugins/clone-app/tests/smoke-structure.sh`, replace:

```bash
for r in stack-recommendation-guide effort-estimation-guide infra-cost-guide report-template; do
  must_exist "$P/skills/clone-app/references/$r.md"
done
```

with:

```bash
for r in stack-recommendation-guide effort-estimation-guide infra-cost-guide report-template re-digest-contract; do
  must_exist "$P/skills/clone-app/references/$r.md"
done
```

- [ ] **Step 2: Run the smoke test**

Run: `bash plugins/clone-app/tests/smoke-structure.sh`
Expected: all `PASS` lines including `PASS exists: plugins/clone-app/skills/clone-app/references/re-digest-contract.md`, exit 0.

- [ ] **Step 3: Run the full clone-app suite**

Run: `bash plugins/clone-app/tests/run-all.sh`
Expected: every suite runs; final line `ALL TESTS PASSED`, exit 0. (`run-all.sh` auto-discovers `test-re-digest-contract.sh` via its `test-*.sh` glob — no registration needed.)

- [ ] **Step 4: Verify upstream untouched**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-app/tests/smoke-structure.sh
git commit -m "test(clone-app): register re-digest-contract in smoke structure check"
```

---

## Self-Review

**Spec coverage:**
- Phase 2 probe/dispatch/consume → Task 2 Step 3. ✓
- Subagent isolation (Agent tool, general-purpose) → Task 2 Step 3 Phase 2b. ✓
- Branch decision table (skill / scripts / stop) → Task 2 Step 3 Phase 2a. ✓
- Digest contract (3 files, schemas, RE Method values, framework guard) → Task 1 Step 3. ✓
- Tier-2 payloads for auth/payment/core only → contract doc + Task 2 Phase 2b step 3. ✓
- Durable memory in `$WORK/` (memory option 1) → files written by subagent, consumed on demand. ✓
- Phase 5 reads payloads.json → Task 2 Step 4. ✓
- Phase 6 Backend API Surface section → Task 2 Step 5. ✓
- Error table additions (subagent fail, no digest, both branches missing) → Task 2 Step 6. ✓
- New fixtures + structural tests, offline → Task 1. ✓
- smoke-structure.sh updated → Task 3 Step 1. ✓
- Upstream untouched check → every task's penultimate step + global constraint. ✓
- `resolve-re-scripts.sh` unchanged → not modified in any task. ✓

**Placeholder scan:** No TBD/TODO; every code/doc step shows full content. ✓

**Type consistency:** Filenames (`re-digest.md`, `payloads.json`, `re-summary.txt`), JSON keys (`package`, `re_method`, `endpoints`, `buildconfig`, `request_body`, `response`, `headers`), section headings, and RE Method values (`re-skill`, `direct-scripts`, `limited:`) are identical across the contract doc, fixtures, tests, and SKILL.md assertions. ✓
