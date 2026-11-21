"""pano.py <out.png> "<title>" [--cols=N] [--h=H] "A · label|file.png" "B · label|file.png" ...

Decision board for the user: images at one height, a label above each, a dark background, optional grid.
Put the source game's own frame (or its brightness/quality level) in as one option or as a "reference" cell, and
put every option INTO the game frame, not alone on grey — a board of loose objects hides the real problem.
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


def board(out, title, items, H=1100, cols=None):
    pad, top, lab_h = 16, 110, 52
    cells = []
    for it in items:
        lab, f = it.split("|", 1)
        im = Image.open(f).convert("RGB")
        cells.append((lab, im.resize((round(im.width * H / im.height), H), Image.LANCZOS)))
    cols = cols or len(cells)
    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    W = max(sum(im.width for _, im in r) + pad * (len(r) + 1) for r in rows)
    c = Image.new("RGB", (W, top - lab_h + len(rows) * (H + lab_h + pad)), (24, 24, 30))
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
    c.save(out)
    return c.size


if __name__ == "__main__":
    opts = dict(a[2:].split("=") for a in sys.argv[3:] if a.startswith("--"))
    items = [a for a in sys.argv[3:] if not a.startswith("--")]
    print(sys.argv[1], board(sys.argv[1], sys.argv[2], items, int(opts.get("h", 1100)),
                             int(opts["cols"]) if "cols" in opts else None))
