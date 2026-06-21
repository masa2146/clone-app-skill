#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "fetch-charts.py")
FIXTURE = os.path.join(HERE, "fixtures", "rss-sample.json")

def run():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "topfreeapplications",
         "--region", "us", "--json-file", FIXTURE])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    check("feed", d["feed"] == "topfreeapplications")
    check("region", d["region"] == "us")
    check("count", d["count"] == 2)
    e0 = d["entries"][0]
    check("rank 1", e0["rank"] == 1)
    check("name", e0["name"] == "Puzzle Quest Saga")
    check("developer", e0["developer"] == "Casual Studio")
    check("category", e0["category"] == "Games")
    check("bundle_id", e0["bundle_id"] == "com.casual.puzzlequest")
    check("price", e0["price"] == "0.00000")
    e1 = d["entries"][1]
    check("rank 2", e1["rank"] == 2)
    check("second name", e1["name"] == "Budget Buddy")
    for k in ["rank", "name", "developer", "category", "bundle_id", "price"]:
        check(f"key present: {k}", k in e0)
    sys.exit(1 if fails else 0)

main()
