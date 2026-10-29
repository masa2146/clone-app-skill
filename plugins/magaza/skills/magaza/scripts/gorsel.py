#!/usr/bin/env python3
"""Store screenshots and feature graphics in three distinct styles, for every language.

    gorsel.py --plan Docs/store/magaza-plani.json --cikti <dir> [--stil serit,panorama,odak] [--dil tr-TR,en-US]

Writes <dir>/<dil>/<stil>/telefon-NN.png (1080x1920, RGB) and grafik.png (1024x500), plus
<dir>/manifest.json, which denetle.py and sayfa.py read. Every frame is real gameplay
from the plan; only the framing and the text differ between styles:

  serit     caption band on top, the gameplay frame as a card below
  panorama  the eight images form one continuous scene: a ribbon runs through all of
            them, cards alternate high/low, captions alternate top/bottom
  odak      blurred gameplay background, one big word, the frame as a tilted card and a
            magnified detail (or the plan's cut-out character) breaking out of it

1080x2400 is not an option: Play rejects a long side over twice the short side.
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak as o  # noqa: E402
from ortak import W, H, GW, GH  # noqa: E402

STYLES = ("serit", "panorama", "odak")


def serit(frame, caption, P, font, spaced):
    img = o.gradient(W, H, P["koyu"], P["ana"])
    area, over = o.text_block(img, caption, font, (60, 70, 1020, 370), P["acik"], P["koyu"], spaced, 112)
    c, pad = o.card(o.cover(frame, 944, 1404), 36, 8, P["vurgu"])
    o.paste_rgba(img, c, (68 - pad, 440 - pad))
    return img, area, over


def panorama(frames, captions, P, font, spaced):
    n = len(frames)
    pano = o.gradient(W * n, H, P["koyu"], P["ana"], vertical=False)
    # a second, slower gradient so neighbouring panels never look alike
    wave = Image.new("L", (W * n, 1))
    for x in range(W * n):
        wave.putpixel((x, 0), int(110 + 90 * math.sin(x / (W * 1.7))))
    pano = Image.composite(pano, o.gradient(W * n, H, P["ana"], P["koyu"]), wave.resize((W * n, H)))
    d = ImageDraw.Draw(pano)
    pts_top, pts_bot = [], []
    for x in range(0, W * n + 1, 20):           # one ribbon through every panel
        y = H * 0.5 + H * 0.36 * math.sin(x / (W * 0.9) + 0.6)
        pts_top.append((x, y - 120))
        pts_bot.append((x, y + 120))
    d.polygon(pts_top + pts_bot[::-1], fill=P["vurgu"])
    out, areas, overs = [], [], []
    for i, (f, cap) in enumerate(zip(frames, captions)):
        high = i % 2 == 1
        cw, ch = 900, 1320
        c, pad = o.card(o.cover(f, cw, ch), 40, 8, P["acik"])
        rot = c.rotate(2.5 if high else -2.5, resample=Image.BICUBIC, expand=True)
        x = i * W + (W - rot.width) // 2
        y = (260 if high else 470) - (rot.height - ch) // 2
        o.paste_rgba(pano, rot, (x, y))
        box = (i * W + 60, 1640, i * W + 1020, 1880) if high else (i * W + 60, 60, i * W + 1020, 380)
        a, ov = o.text_block(pano, cap, font, box, P["acik"], P["koyu"], spaced, 104)
        areas.append(a)
        overs.append(ov)
    for i in range(n):
        out.append(pano.crop((i * W, 0, (i + 1) * W, H)))
    return out, areas, overs, pano


def odak(frame, hero, caption, P, font, spaced):
    img = o.cover(frame, W, H).filter(ImageFilter.GaussianBlur(22))
    img = Image.blend(img, Image.new("RGB", (W, H), P["koyu"]), 0.55)
    words = caption.split(" ", 1) if spaced else [caption]
    a1, ov1 = o.text_block(img, words[0], font, (60, 90, 1020, 330), o.readable(P["koyu"], P["vurgu"], P["acik"]),
                           P["koyu"], spaced, 210,
                           max_lines=1 if spaced else 2)
    a2, ov2 = (o.text_block(img, words[1], font, (60, 330, 1020, 470), P["acik"], P["koyu"], spaced, 84)
               if len(words) > 1 else (0, False))
    cw, ch = 760, 1150
    c, pad = o.card(o.cover(frame, cw, ch), 36, 8, P["acik"])
    rot = c.rotate(-3, resample=Image.BICUBIC, expand=True)
    o.paste_rgba(img, rot, ((W - rot.width) // 2, 560 - (rot.height - ch) // 2))
    if hero is not None:
        hr = hero.convert("RGBA")
        s = min(620 / hr.width, 760 / hr.height)
        hr = hr.resize((int(hr.width * s), int(hr.height * s)), Image.LANCZOS)
        o.paste_rgba(img, hr, (W - hr.width - 20, H - hr.height - 30))
    else:                                        # magnifier on the frame's centre
        dia = 440
        src = o.cover(frame, cw, ch)
        z = src.crop((cw // 2 - 120, ch // 2 - 120, cw // 2 + 120, ch // 2 + 120)).resize((dia, dia), Image.LANCZOS)
        m = Image.new("L", (dia, dia), 0)
        ImageDraw.Draw(m).ellipse((0, 0, dia, dia), fill=255)
        ring = Image.new("RGBA", (dia + 32, dia + 32), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((0, 0, dia + 31, dia + 31), fill=P["vurgu"])
        ring.paste(z, (16, 16), m)
        o.paste_rgba(img, ring, (W - dia - 70, H - dia - 110))
    return img, a1 + a2, ov1 or ov2


def grafik(style, frames, pano, hero, slogan, title, P, font, spaced, logo):
    if style == "panorama" and pano is not None:
        s = GH / pano.height
        wide = pano.resize((int(pano.width * s), GH), Image.LANCZOS)
        x = (wide.width - GW) // 2
        g = wide.crop((x, 0, x + GW, GH))
        pill = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle((170, 150, 854, 350), 40, fill=P["koyu"] + (200,))
        o.paste_rgba(g, pill, (0, 0))
        o.text_block(g, slogan or title, font, (200, 165, 824, 335), P["acik"], None, spaced, 80)
        return g
    if style == "odak":
        g = o.cover(frames[0], GW, GH).filter(ImageFilter.GaussianBlur(14))
        g = Image.blend(g, Image.new("RGB", (GW, GH), P["koyu"]), 0.5)
        if hero is not None:
            hr = hero.convert("RGBA")
            s = 440 / hr.height
            hr = hr.resize((int(hr.width * s), 440), Image.LANCZOS)
            o.paste_rgba(g, hr, (GW - hr.width - 60, GH - 440 - 10))
        else:
            dia = 340
            z = o.cover(frames[0], dia, dia)
            m = Image.new("L", (dia, dia), 0)
            ImageDraw.Draw(m).ellipse((0, 0, dia, dia), fill=255)
            ImageDraw.Draw(g).ellipse((GW - dia - 94, 64, GW - 66, 64 + dia + 28), fill=P["vurgu"])
            g.paste(z, (GW - dia - 80, 78), m)
        o.text_block(g, slogan or title, font, (60, 120, 600, 380), o.readable(P["koyu"], P["vurgu"], P["acik"]),
                     P["koyu"], spaced, 96, align="left")
        return g
    g = o.gradient(GW, GH, P["koyu"], P["ana"], vertical=False)
    if logo:
        lg = Image.open(logo).convert("RGBA")
        s = min(460 / lg.width, 200 / lg.height)
        lg = lg.resize((int(lg.width * s), int(lg.height * s)), Image.LANCZOS)
        o.paste_rgba(g, lg, (300 - lg.width // 2, 80))
    else:
        o.text_block(g, title, font, (70, 70, 540, 260), P["acik"], P["koyu"], spaced, 90)
    o.text_block(g, slogan, font, (70, 280, 540, 430), o.readable(P["koyu"], P["vurgu"], P["acik"]), P["koyu"], spaced, 56)
    c, pad = o.card(o.cover(frames[0], 360, 420), 24, 6, P["vurgu"])
    o.paste_rgba(g, c, (620 - pad, 40 - pad))
    return g


def render(plan, out_dir, styles=STYLES, langs=None):
    frames = [Image.open(p) for p in plan["kareler"]][:8]
    if len(frames) < 3:
        sys.exit("ERROR: at least 3 gameplay frames (Play: 3 portrait screenshots for games)")
    heroes = [Image.open(p) for p in plan.get("odak") or []]
    P = o.palette(plan, frames)
    rows = []
    for loc, t in plan["diller"].items():
        if langs and loc not in langs:
            continue
        font = o.font_for(plan, loc)
        spaced = o.lang_info(loc).get("bosluk", True)
        caps = (t.get("basliklar") or [])[:len(frames)]
        caps += [""] * (len(frames) - len(caps))
        for st in styles:
            d = os.path.join(out_dir, loc, st)
            os.makedirs(d, exist_ok=True)
            pano = None
            if st == "panorama":
                imgs, areas, overs, pano = panorama(frames, caps, P, font, spaced)
            else:
                imgs, areas, overs = [], [], []
                for i, (f, cap) in enumerate(zip(frames, caps)):
                    hero = heroes[i % len(heroes)] if heroes else None
                    im, a, ov = serit(f, cap, P, font, spaced) if st == "serit" else odak(f, hero, cap, P, font, spaced)
                    imgs.append(im)
                    areas.append(a)
                    overs.append(ov)
            for i, (im, a, ov) in enumerate(zip(imgs, areas, overs), 1):
                p = os.path.join(d, f"telefon-{i:02d}.png")
                im.convert("RGB").save(p, optimize=True)
                rows.append({"dil": loc, "stil": st, "tur": "telefon", "sira": i, "yol": os.path.abspath(p),
                             "metin": caps[i - 1], "metin_orani": round(a / (W * H), 4), "tasma": ov})
            g = grafik(st, frames, pano, heroes[0] if heroes else None, t.get("grafik", ""),
                       t.get("ad") or plan.get("oyun", ""), P, font, spaced, plan.get("logo"))
            p = os.path.join(d, "grafik.png")
            g.convert("RGB").save(p, optimize=True)
            rows.append({"dil": loc, "stil": st, "tur": "grafik", "yol": os.path.abspath(p),
                         "metin": t.get("grafik", "")})
    man = {"oyun": plan.get("oyun"), "palet": {k: "#%02x%02x%02x" % v for k, v in P.items()},
           "stiller": list(styles), "goruntuler": rows}
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    return man


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", required=True)
    ap.add_argument("--cikti", required=True)
    ap.add_argument("--stil", default=",".join(STYLES))
    ap.add_argument("--dil")
    a = ap.parse_args(argv)
    styles = [s for s in a.stil.split(",") if s]
    bad = [s for s in styles if s not in STYLES]
    if bad:
        sys.exit(f"ERROR: unknown style {bad}; choose from {STYLES}")
    man = render(o.load_plan(a.plan), a.cikti, styles, a.dil.split(",") if a.dil else None)
    n = sum(r["tur"] == "telefon" for r in man["goruntuler"])
    print(f"{n} ekran görüntüsü + {len(man['goruntuler']) - n} özellik grafiği -> {os.path.abspath(a.cikti)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
