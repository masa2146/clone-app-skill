#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "fetch-play-charts.py")
FIXTURE = os.path.join(HERE, "fixtures", "play-chart.html")

def run():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "top", "--region", "US", "--html-file", FIXTURE])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    check("source", d["source"] == "google-play")
    check("chart", d["chart"] == "top")
    check("region", d["region"] == "US")
    check("count (dedup app1 repeat)", d["count"] == 2)
    e0 = d["entries"][0]
    check("rank 1", e0["rank"] == 1)
    check("name", e0["name"] == "Habit Tracker")
    check("package", e0["package"] == "com.example.habit")
    check("rating", e0["rating"] == 4.6)
    for k in ["rank", "name", "package", "rating"]:
        check(f"key present: {k}", k in e0)
    check("second package", d["entries"][1]["package"] == "com.example.budget")
    check("second name", d["entries"][1]["name"] == "Budget Buddy")
    sys.exit(1 if fails else 0)

main()
