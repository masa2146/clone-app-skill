"""Shared pieces for the store scripts: plan loading, per-language fonts, text fitting,
palette, image helpers. Pillow + fontTools; no project paths baked in.

The plan (Docs/store/magaza-plani.json in the game repo; paths relative to it):

    {"oyun": "Name", "font": "fonts/Game.ttf", "fontlar": {"ja": "...", "ko": "..."},
     "palet": {"koyu": "#1b1030", "ana": "#5a2ca0", "vurgu": "#ffc23d", "acik": "#fff6e4"},
     "kareler": ["captures/01.png", ... up to 8, real gameplay],
     "odak": ["hero.png", ...],            # optional cut-outs with alpha, style "odak"
     "logo": "logo.png",                   # optional, feature graphic
     "diller": {"tr-TR": {"ad": "", "kisa": "", "uzun": "", "basliklar": [8 captions],
                          "grafik": "slogan", "fragman": [one caption per segment], "kapanis": ""}},
     "fragman": {...}                      # see fragman.py
    }
"""
import json
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "reference")
W, H = 1080, 1920
GW, GH = 1024, 500
NO_LINE_START = set("ー、。，．・：；？！」』）〕］｝〉》ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ々,.!?)]}")


def load_plan(path):
    with open(path) as f:
        plan = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    res = lambda p: p if not p or os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    for k in ("font", "logo"):
        if plan.get(k):
            plan[k] = res(plan[k])
    for k in ("kareler", "odak"):
        plan[k] = [res(p) for p in plan.get(k) or []]
    plan["fontlar"] = {k: res(v) for k, v in (plan.get("fontlar") or {}).items()}
    fr = plan.get("fragman") or {}
    for b in fr.get("bolumler") or []:
        b["klip"] = res(b["klip"])
    if fr.get("muzik"):
        fr["muzik"] = res(fr["muzik"])
    plan["_base"] = base
    return plan


@lru_cache(None)
def languages():
    with open(os.path.join(REF, "diller.json")) as f:
        return json.load(f)["diller"]


def lang_info(loc):
    return languages().get(loc) or languages().get(loc.split("-")[0]) or {"yon": "ltr", "bosluk": True,
                                                                          "baslik": [], "aciklama": []}


def font_for(plan, loc):
    f = plan.get("fontlar") or {}
    return f.get(loc) or f.get(loc.split("-")[0]) or plan["font"]


@lru_cache(None)
def _cmap(path):
    from fontTools.ttLib import TTFont
    kw = {"fontNumber": 0} if path.lower().endswith((".ttc", ".otc")) else {}
    t = TTFont(path, lazy=True, **kw)
    return frozenset(t.getBestCmap() or {})


def missing_glyphs(font_path, text):
    cm = _cmap(font_path)
    return sorted({c for c in text if not c.isspace() and ord(c) not in cm})


@lru_cache(None)
def _font(path, size):
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, width, spaced):
    lines = []
    for para in text.split("\n"):
        units = para.split(" ") if spaced else list(para)
        cur = ""
        for u in units:
            trial = (cur + " " + u if cur else u) if spaced else cur + u
            if not cur or draw.textlength(trial, font=font) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = u
        lines.append(cur)
    return lines


def _balanced(draw, text, font, width, spaced):
    """Same line count as a greedy wrap, but even lines: no one-word or one-glyph orphan."""
    lines = _wrap(draw, text, font, width, spaced)
    if len(lines) < 2 or "\n" in text:
        return lines
    if not spaced:
        n, chars = len(lines), list(text)
        k = -(-len(chars) // n)
        out = ["".join(chars[i:i + k]) for i in range(0, len(chars), k)]
        for i in range(1, len(out)):     # kinsoku: a line never starts with these
            while out[i] and out[i][0] in NO_LINE_START:
                out[i - 1] += out[i][0]
                out[i] = out[i][1:]
        return [l for l in out if l]
    lo, hi = max(draw.textlength(w, font=font) for w in text.split(" ")), width
    for _ in range(12):
        mid = (lo + hi) / 2
        if len(_wrap(draw, text, font, mid, spaced)) <= len(lines):
            hi = mid
        else:
            lo = mid
    return _wrap(draw, text, font, hi, spaced)


def fit(draw, text, font_path, w, h, max_size, min_size=28, spaced=True, max_lines=3):
    """Largest size whose wrapped text fits w x h; overflow=True if even min_size does not."""
    size = max_size
    while True:
        font = _font(font_path, size)
        lines = _balanced(draw, text, font, w, spaced)
        lh = int(size * 1.15)
        widest = max(draw.textlength(l, font=font) for l in lines)
        if (len(lines) <= max_lines and lh * len(lines) <= h and widest <= w) or size <= min_size:
            return font, lines, lh, not (len(lines) <= max_lines and lh * len(lines) <= h and widest <= w)
        size -= 4


def text_block(img, text, font_path, box, fill, stroke=None, spaced=True, max_size=110, min_size=28,
               max_lines=3, align="center", valign="center"):
    """Draws text fitted into box (x0, y0, x1, y1). Returns (painted area px, overflow)."""
    if not text:
        return 0, False
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    font, lines, lh, overflow = fit(d, text, font_path, x1 - x0, y1 - y0, max_size, min_size, spaced, max_lines)
    sw = max(2, font.size // 14) if stroke else 0
    total = lh * len(lines)
    y = y0 + {"top": 0, "center": (y1 - y0 - total) // 2, "bottom": y1 - y0 - total}[valign]
    area = 0
    for line in lines:
        lw = d.textlength(line, font=font)
        x = {"center": x0 + (x1 - x0 - lw) / 2, "left": x0, "right": x1 - lw}[align]
        d.text((x, y), line, font=font, fill=fill, stroke_width=sw, stroke_fill=stroke)
        bb = d.textbbox((x, y), line, font=font, stroke_width=sw)
        area += (bb[2] - bb[0]) * (bb[3] - bb[1])
        y += lh
    return area, overflow


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def contrast(a, b):
    """WCAG contrast ratio of two RGB colours."""
    def lum(c):
        v = [x / 255 for x in c]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(bg, *choices):
    """First colour that reads on bg (contrast >= 3, Play's large-text floor), else the best one."""
    for c in choices:
        if contrast(c, bg) >= 3:
            return c
    return max(choices, key=lambda c: contrast(c, bg))


def palette(plan, frames):
    """Plan colours, else derived from the gameplay frames: the dominant hue made deep for the
    background, the most saturated other hue made bright for the accent. Muted frame colours
    taken as they are gave grey-brown sets."""
    import colorsys
    if plan.get("palet"):
        return {k: hexrgb(v) for k, v in plan["palet"].items()}
    strip = Image.new("RGB", (64 * len(frames), 64))
    for i, f in enumerate(frames):
        strip.paste(f.convert("RGB").resize((64, 64)), (64 * i, 0))
    counts = strip.quantize(12).convert("RGB").getcolors(64 * 64 * len(frames))
    hsv = [(n, colorsys.rgb_to_hsv(*(v / 255 for v in c))) for n, c in counts]
    tinted = [x for x in hsv if x[1][1] > 0.25] or hsv
    h0 = max(tinted, key=lambda x: x[0])[1][0]
    hue_gap = lambda h: min(abs(h - h0), 1 - abs(h - h0))
    others = [x for x in tinted if hue_gap(x[1][0]) > 0.12] or tinted
    ha = max(others, key=lambda x: x[1][1] * x[1][2] * (x[0] ** 0.25))[1][0]
    rgb = lambda h, s_, v: tuple(int(255 * c) for c in colorsys.hsv_to_rgb(h, s_, v))
    return {"koyu": rgb(h0, 0.70, 0.22), "ana": rgb(h0, 0.60, 0.48),
            "vurgu": rgb(ha, 0.80, 1.0), "acik": rgb(ha, 0.06, 1.0)}


def cover(img, w, h, focus=(0.5, 0.5)):
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    r = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x = int((r.width - w) * focus[0])
    y = int((r.height - h) * focus[1])
    return r.crop((x, y, x + w, y + h))


def gradient(w, h, c1, c2, vertical=True):
    a = Image.new("RGB", (1, 256) if vertical else (256, 1))
    for i in range(256):
        t = i / 255
        a.putpixel((0, i) if vertical else (i, 0), tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))
    return a.resize((w, h), Image.BILINEAR)


def card(img, radius, border, border_col, shadow=True):
    """Rounded card with border and soft shadow, returned as RGBA ready to paste."""
    w, h = img.size
    pad = 40 if shadow else 0
    size = (w + 2 * border + 2 * pad, h + 2 * border + 2 * pad)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    if shadow:
        sh = Image.new("L", size, 0)
        ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 14, size[0] - pad, size[1] - pad + 14),
                                             radius + border, fill=150)
        out = Image.new("RGBA", size, (0, 0, 0, 255))
        out.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((pad, pad, pad + w + 2 * border, pad + h + 2 * border), radius + border, fill=border_col)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w, h), radius, fill=255)
    out.paste(img.convert("RGB"), (pad + border, pad + border), m)
    return out, pad


def paste_rgba(base, im, xy):
    base.paste(im, (int(xy[0]), int(xy[1])), im)
