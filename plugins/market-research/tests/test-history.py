#!/usr/bin/env python3
import json, subprocess, sys, os, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "history.py")
FIX = os.path.join(HERE, "fixtures")

def run(args, stdin_path):
    with open(stdin_path, "rb") as f:
        return subprocess.run([sys.executable, SCRIPT, *args],
                              stdin=f, capture_output=True)

def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    cands = os.path.join(FIX, "candidates-sample.json")

    # filter: against the seed, only "Budget Buddy" survives
    r = run(["filter", "--history", os.path.join(FIX, "history-seed.json")], cands)
    check("filter exit 0", r.returncode == 0)
    survivors = json.loads(r.stdout)
    names = sorted(c["name"] for c in survivors)
    check("filter drops package collision + name collision", names == ["Budget Buddy"])

    # filter against a missing history file = nothing seen, all 3 survive
    tmp = tempfile.mkdtemp()
    try:
        missing = os.path.join(tmp, "nope.json")
        r = run(["filter", "--history", missing], cands)
        check("filter missing-history exit 0", r.returncode == 0)
        check("filter missing-history keeps all", len(json.loads(r.stdout)) == 3)

        # add: appends all 3 to a fresh history, reports counts
        h = os.path.join(tmp, "h.json")
        r = run(["add", "--history", h], cands)
        check("add exit 0", r.returncode == 0)
        rep = json.loads(r.stdout)
        check("add reports added 3", rep["added"] == 3)
        check("add reports total 3", rep["total"] == 3)
        saved = json.load(open(h))
        check("history file has 3 suggestions", len(saved["suggestions"]) == 3)
        check("history entries carry key", all("key" in s for s in saved["suggestions"]))
    finally:
        shutil.rmtree(tmp)

    sys.exit(1 if fails else 0)

main()
