"""pano.py <out.png> "<title>" [--cols=N] [--h=H] [--zoom=fx,fy,fw,fh] [--note="..."] "A · label|file.png" ...

Decision board for the user: images at one height, a label above each, a dark background, optional grid.
--zoom adds a close-up row: every image is first centre-cropped to the FIRST image's aspect (crop, never stretch:
generators return slightly different aspects), then the same box (fractions of the frame) is cut from each, so the
close-ups are directly comparable. --note adds a line under the board for defects the generator made (a drifted HUD,
a misplaced group) — they are noted, never retouched.
Put every option INTO the game frame, not alone on grey. The source game's own frame may be a labelled reference
cell on the board; it never goes to a generator.
"""
import sys

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def to_aspect(im, aspect):
    w, h = im.size
    if w / h > aspect:
        nw = round(h * aspect)
        return im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = round(w / aspect)
    return im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def board(out, title, items, H=1100, cols=None, zoom=None, note=None):
    pad, top, lab_h = 16, 110, 52
    loaded = [(lab, Image.open(f).convert("RGB")) for lab, f in (it.split("|", 1) for it in items)]
    cells = [(lab, im.resize((round(im.width * H / im.height), H), Image.LANCZOS)) for lab, im in loaded]
    cols = cols or len(cells)
    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    if zoom:
        fx, fy, fw, fh = zoom
        aspect = loaded[0][1].width / loaded[0][1].height
        zc = []
        for lab, im in loaded:
            im = to_aspect(im, aspect)
            W0, H0 = im.size
            z = im.crop((round(fx * W0), round(fy * H0), round((fx + fw) * W0), round((fy + fh) * H0)))
            zc.append((lab.split("·")[0].strip() + " · yakın", z.resize((round(z.width * H / z.height), H), Image.LANCZOS)))
        rows += [zc[i:i + cols] for i in range(0, len(zc), cols)]
    W = max(sum(im.width for _, im in r) + pad * (len(r) + 1) for r in rows)
    note_h = 60 if note else 0
    c = Image.new("RGB", (W, top - lab_h + len(rows) * (H + lab_h + pad) + note_h), (24, 24, 30))
    d = ImageDraw.Draw(c)
    d.text((pad, 14), title, font=font(38), fill=(255, 255, 255))
    y = top
    for r in rows:
        x = pad
        for lab, im in r:
            c.paste(im, (x, y))
            d.text((x + 6, y - 42), lab, font=font(30), fill=(255, 220, 110))
            x += im.width + pad
        y += H + lab_h + pad
    if note:
        d.text((pad, y - lab_h + 8), note, font=font(28), fill=(255, 150, 150))
    c.save(out)
    return c.size


if __name__ == "__main__":
    opts = dict(a[2:].split("=", 1) for a in sys.argv[3:] if a.startswith("--"))
    items = [a for a in sys.argv[3:] if not a.startswith("--")]
    zoom = tuple(map(float, opts["zoom"].split(","))) if "zoom" in opts else None
    print(sys.argv[1], board(sys.argv[1], sys.argv[2], items, int(opts.get("h", 1100)),
                             int(opts["cols"]) if "cols" in opts else None, zoom, opts.get("note")))
