#!/usr/bin/env python3
"""Best-effort check whether an iOS App Store equivalent exists, via the
public iTunes Search API. There is no reliable Android-package → App-Store-ID
mapping, so we search by term (app title) and return the top matches."""
import sys, json, argparse, urllib.request, urllib.parse, ssl, subprocess, shutil

UA = "Mozilla/5.0"

def _http_get(url):
    """GET a URL; on an SSL trust failure (macOS system Python ships without a
    CA bundle) fall back to the system `curl`. Stdlib-only, no pip."""
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

def fetch(term):
    q = urllib.parse.urlencode({"term": term, "entity": "software", "limit": 5})
    url = f"https://itunes.apple.com/search?{q}"
    return json.loads(_http_get(url))

def shape(data):
    results = []
    for r in data.get("results", []):
        results.append({
            "name": r.get("trackName"),
            "seller": r.get("sellerName"),
            "rating": r.get("averageUserRating"),
            "rating_count": r.get("userRatingCount"),
            "price": r.get("formattedPrice"),
            "url": r.get("trackViewUrl"),
        })
    return {"found": len(results) > 0, "source": "app-store", "results": results}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("term")
    ap.add_argument("--json-file")
    args = ap.parse_args()

    if args.json_file:
        with open(args.json_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        try:
            data = fetch(args.term)
        except Exception as e:
            print(json.dumps({"found": False, "source": "app-store",
                              "results": [], "error": str(e)}, indent=2))
            sys.exit(0)

    print(json.dumps(shape(data), indent=2))

if __name__ == "__main__":
    main()
