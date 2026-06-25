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
