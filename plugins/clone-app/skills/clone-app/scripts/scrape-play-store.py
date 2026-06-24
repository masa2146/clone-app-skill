#!/usr/bin/env python3
"""Scrape a Google Play store page into a metrics JSON object.

Primary source is the embedded ld+json SoftwareApplication block (stable).
Falls back to light regex for installs/updated which aren't always in ld+json.
"""
import sys, json, re, argparse, urllib.request, ssl, subprocess, shutil

KEYS = ["package", "title", "rating", "rating_count", "installs",
        "category", "developer", "updated", "source",
        "screenshot_urls", "feature_graphic", "description"]

UA = "Mozilla/5.0"

def _http_get(url):
    """GET a URL as text. Try urllib first; on an SSL trust failure (common on
    macOS' system Python, which ships without a CA bundle) fall back to the
    system `curl`, which uses the OS trust store. Stdlib-only, no pip."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLError):
            raise
        if not shutil.which("curl"):
            raise
        out = subprocess.run(
            ["curl", "-sL", "--fail", "-A", UA, url],
            capture_output=True, timeout=60)
        if out.returncode != 0:
            raise
        return out.stdout.decode("utf-8", "replace")

def fetch(package):
    url = f"https://play.google.com/store/apps/details?id={package}&hl=en&gl=US"
    return _http_get(url)

def parse(html, package):
    out = {k: None for k in KEYS}
    out["package"] = package
    out["source"] = "google-play"

    # ld+json SoftwareApplication block. The <script> tag may carry extra
    # attributes (e.g. a CSP nonce="..."), so match any attributes up to '>'.
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
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
            out["description"] = data.get("description")
            img = data.get("image")
            if isinstance(img, list):
                img = img[0] if img else None
            out["feature_graphic"] = img
            shots = data.get("screenshot") or []
            if isinstance(shots, dict):
                shots = [shots]
            urls = []
            for s in shots:
                if isinstance(s, str):
                    urls.append(s)
                elif isinstance(s, dict) and s.get("url"):
                    urls.append(s["url"])
            out["screenshot_urls"] = urls
            break

    # installs (e.g. "1,000,000+"). Play wraps the count and the "Downloads"
    # label in their own elements; the label may be a <span> or a <div>.
    m = re.search(r'([\d,]+\+)\s*</[^>]+>\s*<[^>]*>\s*Downloads', html)
    if not m:
        m = re.search(r'([\d,]+\+)\s*<span>\s*Downloads', html)
    if m:
        out["installs"] = m.group(1)

    # updated date (e.g. "Updated on</div><div ...>Jun 1, 2026</div>" — the
    # label and value live in adjacent elements that may be <span> or <div>).
    m = re.search(r'Updated on\s*</[^>]+>\s*<[^>]*>([^<]+)</[^>]+>', html)
    if not m:
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
