#!/usr/bin/env python3
"""One review page for choosing a style: every language × every style, each row laid out the
way Play shows it (feature graphic, then the screenshot strip), plus a search-result mock.

    sayfa.py <manifest.json> [--fragman fragman.json] [--plan magaza-plani.json] --cikti <dir>/index.html

Image paths are written relative to the page, so the folder can be zipped or published as a
multi-file artifact as it is.
"""
import argparse
import html
import json
import os
import sys
from collections import defaultdict

STYLE_NOTES = {
    "serit": "Şerit — başlık üstte, oyun karesi altta. En okunaklı; kategoride en sık görülen düzen.",
    "panorama": "Panorama — sekiz görüntü yan yana tek sahne. Kaydırırken akış hissi verir.",
    "odak": "Odak — büyük tek sözcük ve yakın plan. Kalabalık arama sonucunda en çok göze çarpan.",
}

CSS = """
:root{--bg:#f4f1ec;--fg:#1d1b19;--muted:#6b655d;--card:#fff;--line:#e2ddd4}
@media (prefers-color-scheme:dark){:root{--bg:#161514;--fg:#efebe5;--muted:#a39b90;--card:#211f1d;--line:#34312d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1280px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}
h2{font-size:18px;margin:36px 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}
.note{color:var(--muted);margin:0 0 12px}.row{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:14px;margin:12px 0}.row h3{margin:0 0 8px;font-size:15px}.strip{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px}
.strip img{height:300px;border-radius:10px;flex:none}.strip img.fg{height:300px;aspect-ratio:1024/500}
.serp{display:flex;gap:12px;align-items:flex-start;margin-top:10px}.serp .t{font-weight:600}.serp img{height:150px;border-radius:8px}
.warn{color:#b3261e}.langs a{margin-right:10px}video{height:360px;border-radius:10px;margin-right:8px}
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("manifest")
    ap.add_argument("--fragman")
    ap.add_argument("--plan")
    ap.add_argument("--cikti", required=True)
    a = ap.parse_args(argv)
    man = json.load(open(a.manifest))
    plan = json.load(open(a.plan)) if a.plan else {}
    vids = json.load(open(a.fragman))["videolar"] if a.fragman else []
    base = os.path.dirname(os.path.abspath(a.cikti))
    rel = lambda p: os.path.relpath(p, base)
    by = defaultdict(lambda: defaultdict(list))
    for r in man["goruntuler"]:
        by[r["dil"]][r["stil"]].append(r)
    e = html.escape
    out = [f"<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Mağaza Seçenekleri</title><style>{CSS}</style></head><body><main>",
           f"<h1>{e(man.get('oyun') or '')} — mağaza seçenekleri</h1>",
           "<p class='note'>Her satır Play'deki sırayla: özellik grafiği, sonra ekran görüntüleri. Bir stil seç; "
           "öbür ikisi yayından sonra Play'in mağaza girişi denemesinde (A/B) varyant olur.</p>",
           "<p class='langs'>" + " ".join(f"<a href='#{e(l)}'>{e(l)}</a>" for l in by) + "</p>"]
    for loc, styles in by.items():
        t = (plan.get("diller") or {}).get(loc, {})
        out.append(f"<h2 id='{e(loc)}'>{e(loc)}</h2>")
        if t:
            out.append(f"<p class='note'><b>{e(t.get('ad', ''))}</b> — {e(t.get('kisa', ''))}</p>")
        for st, rows in styles.items():
            fg = [r for r in rows if r["tur"] == "grafik"]
            shots = sorted((r for r in rows if r["tur"] == "telefon"), key=lambda r: r["sira"])
            flags = [r for r in shots if r.get("tasma") or r.get("metin_orani", 0) > 0.2]
            out.append(f"<div class='row'><h3>{e(STYLE_NOTES.get(st, st))}</h3><div class='strip'>")
            out += [f"<img class='fg' loading='lazy' src='{e(rel(r['yol']))}' alt='özellik grafiği'>" for r in fg]
            out += [f"<img loading='lazy' src='{e(rel(r['yol']))}' alt='{e(r.get('metin') or '')}'>" for r in shots]
            out.append("</div>")
            if flags:
                out.append(f"<p class='warn'>{len(flags)} görselde yazı sığmadı ya da alanın %20'sini aştı.</p>")
            out.append("<div class='serp'>" + "".join(f"<img src='{e(rel(r['yol']))}' alt=''>" for r in shots[:3]) +
                       f"<div><div class='t'>{e(t.get('ad') or man.get('oyun') or '')}</div>"
                       f"<div class='note'>Arama sonucunda ilk üç görüntü böyle görünür.</div></div></div></div>")
        for v in (x for x in vids if x["dil"] == loc):
            out.append(f"<div class='row'><h3>Fragman ({e(v['tur'])}) — {v['sure']} sn, oynanış %{round(100 * v['oynanis_orani'])}</h3>"
                       f"<video controls muted preload='metadata' src='{e(rel(v['yol']))}'></video></div>")
    out.append("</main></body></html>")
    os.makedirs(base, exist_ok=True)
    with open(a.cikti, "w") as f:
        f.write("\n".join(out))
    print(os.path.abspath(a.cikti))
    return 0


if __name__ == "__main__":
    sys.exit(main())
