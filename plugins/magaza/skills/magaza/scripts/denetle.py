#!/usr/bin/env python3
"""Checks a store listing against Play's rules before anything is uploaded.

    denetle.py metin  --plan magaza-plani.json [--rakip rakip.json]   texts: limits, banned words,
                                                                      keyword stuffing, copied phrases
    denetle.py glif   --plan magaza-plani.json                        every glyph the images and the
                                                                      trailer will draw exists in its font
    denetle.py gorsel <manifest.json>                                 sizes, ratio, alpha, text area, count
    denetle.py video  <fragman.json>                                  gameplay share, first gameplay second

Prints one line per finding, `HATA` (blocks the upload) or `UYARI` (fix unless there is a
reason), and exits 1 when there is any HATA. Rules and their sources: reference/play-kurallari.md.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak as o  # noqa: E402

LIMITS = {"ad": 30, "kisa": 80, "uzun": 4000}
NGRAM_WORDS, NGRAM_CHARS = 6, 14      # a shared run this long with a competitor = copied


class Report:
    def __init__(self):
        self.rows = []

    def err(self, *parts):
        self.rows.append(("HATA", " · ".join(map(str, parts))))

    def warn(self, *parts):
        self.rows.append(("UYARI", " · ".join(map(str, parts))))

    def done(self, what):
        for kind, msg in self.rows:
            print(f"{kind}: {msg}")
        n = sum(k == "HATA" for k, _ in self.rows)
        print(f"{what}: {n} hata, {len(self.rows) - n} uyarı")
        return 1 if n else 0


def banned_hits(text, words, spaced):
    low = text.lower()
    hits = []
    for w in words:
        wl = w.lower()
        if spaced and re.match(r"\w", wl[0]) and re.match(r"\w", wl[-1]):
            if re.search(r"(?<!\w)" + re.escape(wl) + r"(?!\w)", low):
                hits.append(w)
        elif wl in low:
            hits.append(w)
    return hits


def tokens(text, spaced):
    text = text.lower()
    if spaced:
        return re.findall(r"\w+", text)
    return [c for c in text if not c.isspace() and c not in "、。，．・！？「」（）"]


def shared_runs(ours, theirs, spaced):
    n = NGRAM_WORDS if spaced else NGRAM_CHARS
    a, b = tokens(ours, spaced), tokens(theirs, spaced)
    grams = {tuple(b[i:i + n]) for i in range(len(b) - n + 1)}
    runs, i = [], 0
    while i <= len(a) - n:
        if tuple(a[i:i + n]) in grams:
            j = i + n
            while j < len(a) and tuple(a[j - n + 1:j + 1]) in grams:
                j += 1
            runs.append((" " if spaced else "").join(a[i:j]))
            i = j
        else:
            i += 1
    return runs


def check_texts(plan, rakip, rep):
    for loc, t in plan["diller"].items():
        info = o.lang_info(loc)
        spaced = info.get("bosluk", True)
        for k, lim in LIMITS.items():
            v = t.get(k) or ""
            if not v:
                rep.err(loc, k, "boş")
            elif len(v) > lim:
                rep.err(loc, k, f"{len(v)} karakter, sınır {lim}")
        strict = [("ad", t.get("ad", "")), ("kisa", t.get("kisa", "")), ("grafik", t.get("grafik", ""))]
        strict += [(f"başlık {i}", c) for i, c in enumerate(t.get("basliklar") or [], 1)]
        strict += [(f"fragman {i}", c) for i, c in enumerate(t.get("fragman") or [], 1)]
        strict += [("kapanış", t.get("kapanis", ""))]
        for field, v in strict:
            for w in banned_hits(v, info.get("baslik", []), spaced):
                rep.err(loc, field, f"Play'in yasakladığı ifade: “{w}”", v)
        uzun = t.get("uzun") or ""
        for w in banned_hits(uzun, info.get("aciklama", []), spaced):
            rep.err(loc, "uzun", f"Play'in yasakladığı ifade: “{w}”")
        ad = t.get("ad") or ""
        if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", ad + t.get("kisa", "")):
            rep.err(loc, "ad/kisa", "emoji yasak")
        if len(ad) > 3 and ad.isupper():
            rep.err(loc, "ad", "tamamı büyük harf yasak (marka değilse)")
        if re.search(r"([!?.*~])\1\1", ad + " " + t.get("kisa", "")):
            rep.err(loc, "ad/kisa", "tekrarlanan özel karakter")
        if t.get("kisa") and uzun.strip().startswith(t["kisa"].strip()):
            rep.warn(loc, "uzun", "kısa açıklamayla aynı başlıyor; Play ilk cümleyi tekrar saymaz")
        words = tokens(uzun, spaced)
        if words:
            common = Counter(w for w in words if len(w) >= (4 if spaced else 2))
            for w, n in common.most_common(3):
                if n >= 8 and n / len(words) > 0.03:
                    rep.err(loc, "uzun", f"“{w}” {n} kez (%{100 * n / len(words):.0f}): anahtar kelime doldurma sayılır")
        for line in uzun.splitlines():
            parts = [p for p in re.split(r"[,،、]", line) if p.strip()]
            if len(parts) >= 7 and sum(len(p.split()) for p in parts) / len(parts) <= 2:
                rep.err(loc, "uzun", "virgülle sıralanmış sözcük listesi (anahtar kelime bloğu)", line[:60])
        for app in (rakip or {}).get("uygulamalar", []):
            other = (app.get("diller") or {}).get(loc) or {}
            for field in ("ad", "kisa", "uzun"):
                for run in shared_runs(t.get(field) or "", other.get("baslik", "") + "\n" + other.get("aciklama", ""), spaced):
                    rep.err(loc, field, f"rakipten kopya: {app['paket']}", f"“{run[:90]}”")


def strings_for(t):
    yield t.get("ad", "")
    yield t.get("grafik", "")
    yield t.get("kapanis", "")
    yield from t.get("basliklar") or []
    yield from t.get("fragman") or []


def check_glyphs(plan, rep):
    from PIL import features
    for loc, t in plan["diller"].items():
        font = o.font_for(plan, loc)
        if not os.path.exists(font):
            rep.err(loc, "yazı tipi yok", font)
            continue
        miss = o.missing_glyphs(font, "".join(strings_for(t)))
        if miss:
            rep.err(loc, os.path.basename(font), "eksik harf: " + "".join(miss[:30]),
                    f"plan.fontlar['{loc.split('-')[0]}'] ile bu dile yazı tipi ver")
        if o.lang_info(loc).get("raqm") and not features.check("raqm"):
            rep.err(loc, "bu yazı harf birleştirme ister (libraqm); Pillow'da yok, harfler kopuk çıkar")


def check_images(man, rep):
    from PIL import Image
    per = Counter()
    for r in man["goruntuler"]:
        p = r["yol"]
        if not os.path.exists(p):
            rep.err(r["dil"], r["stil"], "dosya yok", p)
            continue
        im = Image.open(p)
        w, h = im.size
        where = (r["dil"], r["stil"], os.path.basename(p))
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            rep.err(*where, "alfa kanalı var; Play 24-bit PNG ya da JPEG ister")
        if r["tur"] == "telefon":
            per[(r["dil"], r["stil"])] += 1
            if max(w, h) > 2 * min(w, h):
                rep.err(*where, f"{w}x{h}: uzun kenar kısa kenarın iki katını geçiyor")
            if min(w, h) < 1080 or max(w, h) / min(w, h) < 1.7:
                rep.warn(*where, f"{w}x{h}: oyun önerileri için 9:16 ve en az 1080x1920 gerekir")
            if r.get("metin_orani", 0) > 0.20:
                rep.err(*where, f"yazı alanı %{100 * r['metin_orani']:.0f}, sınır %20")
            if r.get("tasma"):
                rep.err(*where, "başlık en küçük boyda da sığmadı; kısalt", r.get("metin", ""))
        elif r["tur"] == "grafik":
            if (w, h) != (1024, 500):
                rep.err(*where, f"{w}x{h}: özellik grafiği tam 1024x500 olmalı")
        if os.path.getsize(p) > 8 * 1024 * 1024:
            rep.err(*where, "8 MB'tan büyük")
    for (loc, st), n in per.items():
        if n < 3:
            rep.err(loc, st, f"{n} ekran görüntüsü; oyunlar için en az 3")
        if n > 8:
            rep.err(loc, st, f"{n} ekran görüntüsü; en fazla 8")


def check_video(meta, rep):
    for v in meta.get("videolar", []):
        where = (v["dil"], os.path.basename(v["yol"]))
        if v["oynanis_orani"] < 0.80:
            rep.err(*where, f"oynanış %{100 * v['oynanis_orani']:.0f}; Play en az %80 önerir")
        if v["ilk_oynanis_sn"] > 10:
            rep.err(*where, f"oynanış {v['ilk_oynanis_sn']:.1f}. saniyede başlıyor; ilk 10 saniye içinde olmalı")
        if not os.path.exists(v["yol"]):
            rep.err(*where, "dosya yok")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("metin")
    m.add_argument("--plan", required=True)
    m.add_argument("--rakip")
    g = sub.add_parser("glif")
    g.add_argument("--plan", required=True)
    i = sub.add_parser("gorsel")
    i.add_argument("manifest")
    v = sub.add_parser("video")
    v.add_argument("meta")
    a = ap.parse_args(argv)
    rep = Report()
    if a.cmd == "metin":
        rakip = json.load(open(a.rakip)) if a.rakip else None
        check_texts(o.load_plan(a.plan), rakip, rep)
    elif a.cmd == "glif":
        check_glyphs(o.load_plan(a.plan), rep)
    elif a.cmd == "gorsel":
        check_images(json.load(open(a.manifest)), rep)
    else:
        check_video(json.load(open(a.meta)), rep)
    return rep.done(a.cmd)


if __name__ == "__main__":
    sys.exit(main())
