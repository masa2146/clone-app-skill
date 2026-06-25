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
