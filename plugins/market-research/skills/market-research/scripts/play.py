#!/usr/bin/env python3
"""Resolve an app name to a Google Play link + stats, and measure saturation.

Subcommands:
  resolve "<name>"  -> top Play apps hit: package, play_url, rating, installs,
                       last_updated, developer (1-2 links per candidate upstream).
  count   "<query>" -> saturation: how many distinct apps + avg rating on the
                       first Play search results page.

Play search (play.google.com/store/search?q=...&c=apps&hl=en&gl=US) is
server-rendered enough to grep details?id= links + star aria-labels. The details
page carries rating/installs/updated in embedded ld+json (+ light regex), the
same structure clone-app's scrape-play-store.py parses. Stdlib-only, no pip.
"""
import sys, json, re, argparse, urllib.request, urllib.parse, ssl, subprocess, shutil

UA = "Mozilla/5.0"
ID_RE = re.compile(r'/store/apps/details\?id=([\w.]+)')
STAR_RE = re.compile(r'Rated\s+([\d.]+)\s+stars')

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

def _search_html(query, search_file):
    if search_file:
        with open(search_file, encoding="utf-8") as f:
            return f.read()
    q = urllib.parse.quote(query)
    return _http_get(f"https://play.google.com/store/search?q={q}&c=apps&hl=en&gl=US")

def _details_html(package, details_file):
    if details_file:
        with open(details_file, encoding="utf-8") as f:
            return f.read()
    return _http_get(
        f"https://play.google.com/store/apps/details?id={package}&hl=en&gl=US")

def parse_details(html, package):
    out = {"name": None, "developer": None, "rating": None,
           "installs": None, "last_updated": None}
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                         html, re.DOTALL):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "SoftwareApplication":
            out["name"] = data.get("name")
            auth = data.get("author")
            if isinstance(auth, dict):
                out["developer"] = auth.get("name")
            ar = data.get("aggregateRating") or {}
            if ar.get("ratingValue") is not None:
                try: out["rating"] = float(ar["ratingValue"])
                except Exception: pass
            break
    m = re.search(r'([\d,]+\+)\s*</[^>]+>\s*<[^>]*>\s*Downloads', html)
    if not m:
        m = re.search(r'([\d,]+\+)\s*<span>\s*Downloads', html)
    if m:
        out["installs"] = m.group(1)
    m = re.search(r'Updated on\s*</[^>]+>\s*<[^>]*>([^<]+)</[^>]+>', html)
    if not m:
        m = re.search(r'Updated on\s*<span>([^<]+)</span>', html)
    if m:
        out["last_updated"] = m.group(1).strip()
    return out

def cmd_resolve(args):
    html = _search_html(args.query, args.search_file)
    m = ID_RE.search(html)
    res = {"query": args.query, "name": None, "package": None, "play_url": None,
           "rating": None, "installs": None, "last_updated": None, "developer": None}
    if not m:
        print(json.dumps(res, indent=2))
        return
    package = m.group(1)
    res["package"] = package
    res["play_url"] = f"https://play.google.com/store/apps/details?id={package}"
    details = _details_html(package, args.details_file)
    res.update(parse_details(details, package))
    print(json.dumps(res, indent=2))

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("resolve")
    pr.add_argument("query")
    pr.add_argument("--search-file")
    pr.add_argument("--details-file")
    args = ap.parse_args()
    if args.cmd == "resolve":
        try:
            cmd_resolve(args)
        except Exception as e:
            print(f"ERROR: play resolve failed: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
