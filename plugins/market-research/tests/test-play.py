#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "market-research", "scripts", "play.py")
SEARCH = os.path.join(HERE, "fixtures", "play-search.html")
DETAILS = os.path.join(HERE, "fixtures", "play-details.html")

def run(*args):
    return json.loads(subprocess.check_output([sys.executable, SCRIPT, *args]))

def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    r = run("resolve", "Habit Tracker", "--search-file", SEARCH, "--details-file", DETAILS)
    check("package", r["package"] == "com.example.habit")
    check("play_url", r["play_url"] == "https://play.google.com/store/apps/details?id=com.example.habit")
    check("name", r["name"] == "Habit Tracker")
    check("rating", r["rating"] == 4.6)
    check("installs", r["installs"] == "5,000,000+")
    check("last_updated", r["last_updated"] == "Jun 1, 2026")
    check("developer", r["developer"] == "Focus Labs")

    sys.exit(1 if fails else 0)

main()
