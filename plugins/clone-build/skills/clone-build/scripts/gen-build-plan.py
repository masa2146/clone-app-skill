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
