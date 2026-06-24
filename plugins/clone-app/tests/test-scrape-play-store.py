#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "scrape-play-store.py")
FIXTURE = os.path.join(HERE, "fixtures", "play-sample.html")

def run():
    out = subprocess.check_output(
        [sys.executable, SCRIPT, "com.example.app", "--html-file", FIXTURE])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    check("package", d["package"] == "com.example.app")
    check("title", d["title"] == "Example App")
    check("rating", abs((d["rating"] or 0) - 4.3) < 0.001)
    check("rating_count", d["rating_count"] == 12873)
    check("developer", d["developer"] == "Example Studio")
    check("category", d["category"] == "GAME_PUZZLE")
    check("installs", d["installs"] == "1,000,000+")
    check("updated", d["updated"] == "Jun 1, 2026")
    check("source", d["source"] == "google-play")
    check("description", d["description"] == "An example puzzle app.")
    check("feature_graphic", d["feature_graphic"] == "https://play-lh.googleusercontent.com/feature.png")
    check("screenshot count", len(d["screenshot_urls"]) == 2)
    check("screenshot url", d["screenshot_urls"][0] == "https://play-lh.googleusercontent.com/shot1.png")
    # all expected keys present even if null
    for k in ["package","title","rating","rating_count","installs","category","developer","updated","source","screenshot_urls","feature_graphic","description"]:
        check(f"key present: {k}", k in d)
    sys.exit(1 if fails else 0)

main()
