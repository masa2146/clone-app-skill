#!/usr/bin/env python3
"""Fetch an AppBrain Play-store top-chart into a normalized JSON list.

Google Play has no public chart feed and renders via obfuscated batchexecute
JS. AppBrain (appbrain.com) publishes server-rendered HTML top-chart pages with
REAL Android package names. This scrapes those rows. Stdlib-only, no pip.

Unlike Apple's RSS (iOS bundle ids), entries here carry Android packages usable
directly for a clone-app handoff.
"""
import sys, json, re, argparse, urllib.request, ssl, subprocess, shutil

CHARTS = {
    "popular": "https://www.appbrain.com/apps/popular/",
    "top-grossing": "https://www.appbrain.com/apps/highest-grossing/",
    "top-new": "https://www.appbrain.com/apps/new/",
}
UA = "Mozilla/5.0"

def _http_get(url):
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

# One app row: a link to /app/<slug>/<package> followed (within the same row
# block) by developer / category / rating / installs spans.
ROW = re.compile(
    r'href="/app/[^"/]+/(?P<package>[\w.]+)"[^>]*>(?P<name>[^<]+)</a>'
    r'(?P<rest>.*?)(?=href="/app/|</div>\s*</div>|$)', re.DOTALL)
DEV = re.compile(r'class="developer"[^>]*>([^<]+)<')
CAT = re.compile(r'class="category"[^>]*>([^<]+)<')
RAT = re.compile(r'class="rating"[^>]*>\s*([\d.]+)\s*<')
INST = re.compile(r'class="installs"[^>]*>\s*([\d,]+\+)\s*<')

def _first(rx, text):
    m = rx.search(text)
    return m.group(1).strip() if m else None

def parse(html, chart, region, limit):
    entries = []
    for i, m in enumerate(ROW.finditer(html), start=1):
        if i > limit:
            break
        rest = m.group("rest")
        rating = _first(RAT, rest)
        entries.append({
            "rank": i,
            "name": m.group("name").strip(),
            "developer": _first(DEV, rest),
            "category": _first(CAT, rest),
            "package": m.group("package"),
            "rating": float(rating) if rating else None,
            "installs": _first(INST, rest),
        })
    return {"source": "appbrain", "chart": chart, "region": region,
            "count": len(entries), "entries": entries}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chart", choices=sorted(CHARTS))
    ap.add_argument("--region", default="us")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--html-file")
    args = ap.parse_args()

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()
    else:
        try:
            html = _http_get(CHARTS[args.chart])
        except Exception as e:
            print(f"ERROR: failed to fetch AppBrain chart: {e}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps(parse(html, args.chart, args.region, args.limit), indent=2))

if __name__ == "__main__":
    main()
