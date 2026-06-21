#!/usr/bin/env python3
"""Fetch an Apple App Store RSS chart feed into a normalized JSON list.

Apple publishes public, no-auth RSS chart feeds as JSON at
https://itunes.apple.com/<region>/rss/<feed>/limit=<n>/json . They give a
ranked list of trending apps (name, developer, category, iOS bundle id, price).

This is iOS chart data — bundle ids are iOS bundle ids, NOT Android packages.
The market-research skill uses these as trend signal and resolves a Google Play
package later (Phase 5) before any clone-app handoff. Stdlib-only, no pip.
"""
import sys, json, argparse, urllib.request, ssl, subprocess, shutil

FEEDS = ("topfreeapplications", "toppaidapplications", "topgrossingapplications")
UA = "Mozilla/5.0"

def _http_get(url):
    """GET a URL as text. urllib first; on an SSL trust failure (macOS system
    Python ships without a CA bundle) fall back to system `curl`."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
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

def fetch(feed, region, limit):
    url = f"https://itunes.apple.com/{region}/rss/{feed}/limit={limit}/json"
    return json.loads(_http_get(url))

def _label(node):
    """Apple wraps text values as {"label": "..."}; return the label or None."""
    if isinstance(node, dict):
        return node.get("label")
    return None

def normalize(data):
    entries = []
    feed = data.get("feed") or {}
    raw = feed.get("entry") or []
    if isinstance(raw, dict):   # Apple collapses a single entry to a dict
        raw = [raw]
    for i, e in enumerate(raw, start=1):
        cat = (e.get("category") or {}).get("attributes") or {}
        idattr = (e.get("id") or {}).get("attributes") or {}
        price = (e.get("im:price") or {}).get("attributes") or {}
        entries.append({
            "rank": i,
            "name": _label(e.get("im:name")),
            "developer": _label(e.get("im:artist")),
            "category": cat.get("label"),
            "bundle_id": idattr.get("im:bundleId"),
            "price": price.get("amount"),
        })
    return entries

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("feed", choices=FEEDS)
    ap.add_argument("--region", default="us")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json-file")
    args = ap.parse_args()

    if args.json_file:
        with open(args.json_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        try:
            data = fetch(args.feed, args.region, args.limit)
        except Exception as e:
            print(f"ERROR: failed to fetch RSS feed: {e}", file=sys.stderr)
            sys.exit(1)

    entries = normalize(data)
    print(json.dumps({
        "feed": args.feed,
        "region": args.region,
        "count": len(entries),
        "entries": entries,
    }, indent=2))

if __name__ == "__main__":
    main()
