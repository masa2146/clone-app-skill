"""fit.py <raw.png> <out.png> <W>x<H> [--full] [--bottom] [--keep] [tol=14] [holes=0.003]

Cut one object generated on a flat grey (#808080) background and fit it into a W x H canvas.
- Clears the background colour reachable from the border, then every CLOSED region of that colour at least `holes`
  of the image (inside a ring, between table legs). Use holes=0.00005 for small gaps; grey subjects on grey need tol 22.
- Drops loose colourless specks near the background tone, erodes the alpha edge 2 px and softens it (no grey halo).
- Crops to the subject and fits it (2 % margin), centred; --bottom sits it on the bottom edge (figure cut at the knees);
  --keep cuts but does not crop (full-width strip); --full is a full-bleed picture: no cut, centre-crop to W:H and scale.
- box=x,y,w,h: grey subject on grey (fur, steel). Inside the subject box the normal cut (tol) keeps the fur; outside it
  a tight cut (outtol=22, outholes=0.00005) clears the rest. The hole pass can punch the subject's own grey faces
  (armpits, steel parts): shrink `holes` or use box=.
Needs Pillow, numpy, scipy.
"""
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage


def cut(im, tol=14.0, holes=0.003):
    px = np.asarray(im.convert("RGB")).astype(np.int16)
    border = np.concatenate([px[0], px[-1], px[:, 0], px[:, -1]])
    bg = np.median(border, axis=0)
    similar = np.sqrt(((px - bg) ** 2).sum(2)) < tol
    lab, n = ndimage.label(similar)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    drop = [i + 1 for i, s in enumerate(sizes) if (i + 1) in edge or s >= lab.size * holes]
    al = np.where(np.isin(lab, drop), 0, 255).astype(np.uint8)
    lab, n = ndimage.label(al > 20)  # loose grey specks left by a gradient background
    for i in range(1, n + 1):
        m = lab == i
        c = px[m].astype(float)
        if m.sum() < lab.size * 0.01 and np.ptp(c.mean(0)) < 20 and abs(c.mean() - bg.mean()) < 40:
            al[m] = 0
    out = im.convert("RGBA")
    out.putalpha(Image.fromarray(al).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.2)))
    return out


def fit(im, W, H, bottom=False):
    im = im.crop(im.getchannel("A").getbbox())
    s = min(W * 0.96 / im.width, H * (1.0 if bottom else 0.96) / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c.paste(im, ((W - im.width) // 2, H - im.height if bottom else (H - im.height) // 2))
    return c


def main(argv):
    src, out, size = argv[1], argv[2], argv[3]
    W, H = map(int, size.split("x"))
    kw = dict(a.split("=") for a in argv[4:] if "=" in a)
    im = Image.open(src)
    if "--full" in argv:
        im = im.convert("RGB")
        w, h = im.size
        if w / h > W / H:
            nw = round(h * W / H); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w * H / W); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        im.resize((W, H), Image.LANCZOS).save(out)
        return
    tol, holes = float(kw.get("tol", 14)), float(kw.get("holes", 0.003))
    if "box" in kw:
        x, y, w, h = map(int, kw["box"].split(","))
        inner = cut(im, tol, holes)
        outer = cut(im, float(kw.get("outtol", 22)), float(kw.get("outholes", 0.00005)))
        a = np.asarray(outer.getchannel("A")).copy()
        a[y:y + h, x:x + w] = np.asarray(inner.getchannel("A"))[y:y + h, x:x + w]
        im = inner
        im.putalpha(Image.fromarray(a))
    else:
        im = cut(im, tol, holes)
    (im.resize((W, H), Image.LANCZOS) if "--keep" in argv else fit(im, W, H, "--bottom" in argv)).save(out)
    print(out, (W, H))


if __name__ == "__main__":
    main(sys.argv)
