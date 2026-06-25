#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "extract-design.py")
ROOT = os.path.join(HERE, "fixtures", "design-sample")

def run():
    out = subprocess.check_output([sys.executable, SCRIPT, ROOT])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    check("source", d["source"] == "apk-resources")
    check("colors parsed", d["colors"]["values"].get("colorPrimary") == "#FF6200EE")
    check("colors accent", d["colors"]["values"].get("colorAccent") == "#FF03DAC5")
    check("colors confidence high", d["colors"]["confidence"] == "high")
    check("dimens parsed", d["dimens"]["values"].get("spacing_small") == "8dp")
    check("text size dimen", d["dimens"]["values"].get("text_size_body") == "14sp")
    check("theme parent", d["theme"]["values"].get("parent") == "Theme.Material3.DayNight")
    check("theme is_dark flag present", "is_dark" in d["theme"]["values"])
    check("fonts list", "inter_regular.ttf" in d["typography"]["values"]["fonts"])
    check("layout count", d["layouts"]["values"]["count"] == 1)
    for k in ["package","source","framework","colors","dimens","typography","shapes","theme","icon","layouts"]:
        check(f"key present: {k}", k in d)
    sys.exit(1 if fails else 0)

main()
