#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "check-appstore.py")
FIXTURE = os.path.join(HERE, "fixtures", "itunes-sample.json")

def main():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "Example App", "--json-file", FIXTURE])
    d = json.loads(out)
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    check("found true", d["found"] is True)
    check("source", d["source"] == "app-store")
    check("one result", len(d["results"]) == 1)
    r = d["results"][0]
    check("name", r["name"] == "Example App")
    check("seller", r["seller"] == "Example Studio")
    check("rating", abs(r["rating"] - 4.5) < 0.001)
    check("rating_count", r["rating_count"] == 8421)
    check("price", r["price"] == "Free")
    check("url", r["url"].endswith("id123456789"))
    sys.exit(1 if fails else 0)

main()
