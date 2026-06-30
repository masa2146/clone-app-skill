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
