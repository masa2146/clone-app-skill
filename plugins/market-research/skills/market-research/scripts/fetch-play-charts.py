#!/usr/bin/env python3
"""Fetch a play.google.com chart page into a normalized JSON list.

Google Play has no public chart feed, but its server-rendered HTML for
/store/apps/top and /store/apps/category/<CAT> carries ranked app cards with
REAL Android package names (unlike Apple's RSS iOS bundle ids). Each card is an
<a href="/store/apps/details?id=PKG"> wrapping the icon, then a
<div class="Epkrse ">NAME</div> title, then a star aria-label. Play obfuscates
the title class, so the package LINK (stable) is the load-bearing field; name
and rating are best-effort. Stdlib-only, no pip.

(AppBrain, the original plan's source, is Cloudflare-blocked 403 — dropped.)
"""
import sys, json, re, html as _html, argparse, urllib.request, ssl, subprocess, shutil

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

LINK = re.compile(r'href="/store/apps/details\?id=([a-zA-Z0-9._]+)"')
NAME = re.compile(r'class="Epkrse[^"]*"[^>]*>([^<]+)<')
# rating is best-effort: search-style aria-label OR a star-icon followed by a number
RATE_ARIA = re.compile(r'aria-label="Rated\s+([\d.]+)\s+star')
RATE_STAR = re.compile(r'>star</[^>]+>\s*([\d.]+)')

def _chart_url(chart, category, region):
    if chart == "category":
        return f"https://play.google.com/store/apps/category/{category}?hl=en&gl={region}"
    return f"https://play.google.com/store/apps/top?hl=en&gl={region}"

def parse(html, chart_label, region, limit):
    entries = []
    seen = set()
    for m in LINK.finditer(html):
        pkg = m.group(1)
        if pkg in seen:
            continue
        win = html[m.start():m.start() + 1600]   # one card's worth of markup
        nm = NAME.search(win)
        if not nm:
            continue   # icon-only anchor with no title nearby; skip
        seen.add(pkg)
        rt = RATE_ARIA.search(win) or RATE_STAR.search(win)
        entries.append({
            "rank": len(entries) + 1,
            "name": _html.unescape(nm.group(1).strip()),
            "package": pkg,
            "rating": float(rt.group(1)) if rt else None,
        })
        if len(entries) >= limit:
            break
    return {"source": "google-play", "chart": chart_label, "region": region,
            "count": len(entries), "entries": entries}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chart", choices=("top", "category"))
    ap.add_argument("--category")
    ap.add_argument("--region", default="US")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--html-file")
    args = ap.parse_args()

    if args.chart == "category" and not args.category:
        print("ERROR: --category is required for the 'category' chart", file=sys.stderr)
        sys.exit(2)
    chart_label = f"category:{args.category}" if args.chart == "category" else "top"

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()
    else:
        try:
            html = _http_get(_chart_url(args.chart, args.category, args.region))
        except Exception as e:
            print(f"ERROR: failed to fetch Play chart: {e}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps(parse(html, chart_label, args.region, args.limit), indent=2))

if __name__ == "__main__":
    main()
