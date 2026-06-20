#!/usr/bin/env python3
"""Scrape a Google Play store page into a metrics JSON object.

Primary source is the embedded ld+json SoftwareApplication block (stable).
Falls back to light regex for installs/updated which aren't always in ld+json.
"""
import sys, json, re, argparse, urllib.request

KEYS = ["package", "title", "rating", "rating_count", "installs",
        "category", "developer", "updated", "source"]

def fetch(package):
    url = f"https://play.google.com/store/apps/details?id={package}&hl=en&gl=US"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def parse(html, package):
    out = {k: None for k in KEYS}
    out["package"] = package
    out["source"] = "google-play"

    # ld+json SoftwareApplication block
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>',
                         html, re.DOTALL):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "SoftwareApplication":
            out["title"] = data.get("name")
            auth = data.get("author")
            if isinstance(auth, dict):
                out["developer"] = auth.get("name")
            out["category"] = data.get("applicationCategory")
            ar = data.get("aggregateRating") or {}
            if ar.get("ratingValue") is not None:
                try: out["rating"] = float(ar["ratingValue"])
                except Exception: pass
            if ar.get("ratingCount") is not None:
                try: out["rating_count"] = int(ar["ratingCount"])
                except Exception: pass
            break

    # installs (e.g. "1,000,000+")
    m = re.search(r'([\d,]+\+)\s*<span>\s*Downloads', html)
    if m:
        out["installs"] = m.group(1)

    # updated date (e.g. "Updated on<span>Jun 1, 2026</span>")
    m = re.search(r'Updated on\s*<span>([^<]+)</span>', html)
    if m:
        out["updated"] = m.group(1).strip()

    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--html-file")
    args = ap.parse_args()

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            html = f.read()
    else:
        try:
            html = fetch(args.package)
        except Exception as e:
            print(f"ERROR: failed to fetch Play page: {e}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps(parse(html, args.package), indent=2))

if __name__ == "__main__":
    main()
