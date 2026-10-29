#!/usr/bin/env python3
"""Competitor store pages in every target language: what similar games write and show.

    rakip.py <package>... --diller tr-TR,en-US,de-DE --cikti Docs/store/rakip [--gorseller]
    rakip.py <package>... --diller ... --cikti ... --html-dir <dir>   # offline: <pkg>.<locale>.html

Writes rakip.json (title + full description per app per language; denetle.py metin --rakip
uses it to catch copied phrases) and rakip.md: per language, each app's title length, first
sentence, screenshot count, and the words the competitors share — the keywords players search
for in that language. Take structure and keywords from here, never sentences.
--gorseller also downloads their screenshots, to compare layouts, not to reuse.
"""
import argparse
import glob
import importlib.util
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak as o  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def scraper():
    """clone-app's scrape-play-store.py: sibling plugin in a checkout, else the newest cached install."""
    sib = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "clone-app", "skills", "clone-app",
                                        "scripts", "scrape-play-store.py"))
    cands = [sib] if os.path.exists(sib) else sorted(glob.glob(os.path.expanduser(
        "~/.claude/plugins/cache/*/clone-app/*/skills/clone-app/scripts/scrape-play-store.py")), key=os.path.getmtime)
    if not cands:
        sys.exit("ERROR: clone-app plugin not found (its scrape-play-store.py reads the Play page)")
    spec = importlib.util.spec_from_file_location("scrape_play_store", cands[-1])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def first_sentence(text):
    text = (text or "").strip().split("\n")[0]
    m = re.match(r"(.+?[.!?。！？])(\s|$)", text)
    return (m.group(1) if m else text)[:160]


def keywords(texts, spaced, n=20):
    """Words that appear in at least two competitors' pages — shared vocabulary, not one app's brand."""
    seen = Counter()
    for t in texts:
        if spaced:
            words = {w for w in re.findall(r"\w+", t.lower()) if len(w) >= 4 and not w.isdigit()}
        else:
            chars = [c for c in t if not c.isspace()]
            words = {"".join(chars[i:i + 2]) for i in range(len(chars) - 1)}
        seen.update(words)
    return [(w, c) for w, c in seen.most_common(200) if c >= 2][:n]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("packages", nargs="+")
    ap.add_argument("--diller", required=True)
    ap.add_argument("--cikti", required=True)
    ap.add_argument("--html-dir")
    ap.add_argument("--gorseller", action="store_true")
    a = ap.parse_args(argv)
    sp = scraper()
    locs = a.diller.split(",")
    os.makedirs(a.cikti, exist_ok=True)
    apps = []
    for pkg in a.packages:
        entry = {"paket": pkg, "diller": {}}
        for loc in locs:
            info = o.lang_info(loc)
            if a.html_dir:
                p = os.path.join(a.html_dir, f"{pkg}.{loc}.html")
                if not os.path.exists(p):
                    continue
                html = open(p, encoding="utf-8").read()
            else:
                url = f"https://play.google.com/store/apps/details?id={pkg}&hl={info.get('hl', 'en')}&gl={info.get('gl', 'US')}"
                try:
                    html = sp._http_get(url)
                except Exception as e:  # one missing page must not stop the table
                    print(f"WARN: {pkg} {loc}: {e}", file=sys.stderr)
                    continue
            d = sp.parse(html, pkg)
            entry["diller"][loc] = {"baslik": d.get("title") or "", "aciklama": d.get("description") or "",
                                    "ekran_sayisi": len(d.get("screenshot_urls") or []), "puan": d.get("rating"),
                                    "ekranlar": d.get("screenshot_urls") or []}
            if a.gorseller and d.get("screenshot_urls"):
                pj = os.path.join(a.cikti, f"{pkg}.{loc}.json")
                with open(pj, "w") as f:
                    json.dump(d, f)
                sp.download_screenshots(pj, os.path.join(a.cikti, "gorseller", loc, pkg))
        apps.append(entry)
    with open(os.path.join(a.cikti, "rakip.json"), "w") as f:
        json.dump({"uygulamalar": apps}, f, ensure_ascii=False, indent=1)

    md = ["# Rakip mağaza sayfaları", "",
          "Yapı ve anahtar kelime buradan alınır, cümle alınmaz; `denetle.py metin --rakip` kopyayı yakalar.", ""]
    for loc in locs:
        rows = [(x["paket"], x["diller"][loc]) for x in apps if loc in x["diller"]]
        if not rows:
            continue
        md += [f"## {loc}", "", "| Paket | Başlık (karakter) | İlk cümle | Ekran | Puan |", "|---|---|---|---|---|"]
        for pkg, d in rows:
            md.append(f"| {pkg} | {d['baslik']} ({len(d['baslik'])}) | {first_sentence(d['aciklama']).replace('|', '/')} "
                      f"| {d['ekran_sayisi']} | {d['puan'] or '—'} |")
        kw = keywords([d["baslik"] + " " + d["aciklama"] for _, d in rows], o.lang_info(loc).get("bosluk", True))
        md += ["", "Ortak sözcükler: " + (", ".join(f"{w} ({c})" for w, c in kw) or "—"), ""]
    with open(os.path.join(a.cikti, "rakip.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"{len(apps)} rakip × {len(locs)} dil -> {os.path.abspath(a.cikti)}/rakip.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
