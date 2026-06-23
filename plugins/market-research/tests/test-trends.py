#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "trends.py")
FIXTURE = os.path.join(HERE, "fixtures", "trends-sample.json")

def run(*args):
    # exit 0 always (never hard-fails); capture stdout
    out = subprocess.run([sys.executable, SCRIPT, *args],
                         capture_output=True, text=True)
    return out.returncode, json.loads(out.stdout)

def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    rc, d = run("habit tracker", "--json-file", FIXTURE)
    check("exit 0", rc == 0)
    check("ok", d["ok"] is True)
    check("points", d["points"] == 3)
    check("latest_interest", d["latest_interest"] == 100)
    check("avg_interest", d["avg_interest"] == 70.0)  # mean(50,60,100)=70
    check("trend_pct", d["trend_pct"] == 100.0)        # (100-50)/50*100

    # bad fixture -> graceful fallback, still exit 0
    rc2, d2 = run("x", "--json-file", os.path.join(HERE, "fixtures", "play-chart.html"))
    check("fallback exit 0", rc2 == 0)
    check("fallback ok false", d2["ok"] is False)
    check("fallback flag", d2["fallback"] == "websearch")

    sys.exit(1 if fails else 0)

main()
