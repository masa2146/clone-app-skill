#!/usr/bin/env python3
"""Best-effort Google Trends interest signal. NEVER hard-fails.

Google Trends has no API key but the unofficial endpoint needs a token dance
and is fragile under stdlib-only. So: try the live token+timeline flow; on ANY
failure print {"ok": false, "fallback": "websearch"} and exit 0, signalling the
skill to fall back to WebSearch for the same momentum signal. The JSON parser is
unit-tested offline via --json-file. Stdlib-only, no pip.
"""
import sys, json, argparse, urllib.request, urllib.parse, ssl, subprocess, shutil

UA = "Mozilla/5.0"

def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLError):
            raise
        if not shutil.which("curl"):
            raise
        out = subprocess.run(["curl", "-sL", "--fail", "-A", UA, url],
                             capture_output=True, timeout=60)
        if out.returncode != 0:
            raise
        return out.stdout.decode("utf-8", "replace")

def parse_timeline(raw):
    """raw = the timeline JSON (Google prefixes live responses with )]}',  —
    callers strip it first). Returns the computed interest summary dict."""
    data = json.loads(raw)
    points = data["default"]["timelineData"]
    values = [int(p["value"][0]) for p in points if p.get("value")]
    if not values:
        raise ValueError("no timeline values")
    avg = round(sum(values) / len(values), 2)
    first, latest = values[0], values[-1]
    pct = round((latest - first) / first * 100, 2) if first else None
    return {"ok": True, "avg_interest": avg, "latest_interest": latest,
            "trend_pct": pct, "points": len(values)}

def fetch_live(term):
    """Token dance: explore -> widget token -> multiline timeline."""
    base = "https://trends.google.com/trends/api"
    comp = urllib.parse.quote(json.dumps(
        {"comparisonItem": [{"keyword": term, "geo": "", "time": "today 3-m"}],
         "category": 0, "property": ""}))
    explore = _http_get(f"{base}/explore?hl=en-US&tz=0&req={comp}")
    widgets = json.loads(explore.lstrip(")]}',\n"))
    w = next(x for x in widgets["widgets"] if x.get("id") == "TIMESERIES")
    token = w["token"]
    reqobj = urllib.parse.quote(json.dumps(w["request"]))
    tl = _http_get(f"{base}/widgetdata/multiline?hl=en-US&tz=0&req={reqobj}&token={token}")
    return tl.lstrip(")]}',\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("term")
    ap.add_argument("--json-file")
    args = ap.parse_args()

    try:
        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                raw = f.read()
        else:
            raw = fetch_live(args.term)
        res = parse_timeline(raw)
        res["term"] = args.term
        print(json.dumps(res, indent=2))
    except Exception:
        print(json.dumps({"ok": False, "term": args.term,
                          "fallback": "websearch"}, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
