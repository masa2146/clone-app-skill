"""ctx.py <original_sprite.png> <capture.png> <ours.png> <out.jpg> [scale_lo scale_hi] [--full]

In-frame rehearsal, BEFORE anything goes into the engine: find the source game's sprite in a screen capture of the running
game (multi-scale masked template match), erase it (inpaint), drop ours into the same box, and write a sheet:
full capture (original) | close-up original | close-up ours | full capture (ours).
  BOX=x,y,w,h   skip the search (small icons < 100 px mis-match; or the sprite is not visible in this capture)
  FILL=1        large figure on a flat background: fill with the surrounding median instead of inpaint smear
  --full        opaque full-bleed art: only pixels that match the original are replaced
Only the agent looks at the original; it is never uploaded to a generator. Needs opencv-python-headless, Pillow, numpy.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image


def search(C, O, scales, k):
    Ck = cv2.resize(C, (C.shape[1] // k, C.shape[0] // k), interpolation=cv2.INTER_AREA) if k > 1 else C
    best = (-1, None)
    for s in scales:
        w, h = round(O.width * s), round(O.height * s)
        if w < 8 or h < 8 or w > C.shape[1] or h > C.shape[0]:
            continue
        t = np.array(O.resize((max(1, w // k), max(1, h // k)), Image.LANCZOS)).astype(np.float32)
        m = (t[..., 3:4] > 200).astype(np.float32).repeat(3, 2)
        if m.sum() < 30:
            continue
        r = cv2.matchTemplate(Ck, t[..., :3], cv2.TM_CCORR_NORMED, mask=m)
        r[~np.isfinite(r)] = -1
        _, v, _, loc = cv2.minMaxLoc(r)
        if v > best[0]:
            best = (v, (s, (loc[0] * k, loc[1] * k), w, h))
    return best


def main(argv):
    src, cap, ours, out = argv[1:5]
    nums = [float(a) for a in argv[5:] if a[0].isdigit()]
    lo, hi = (nums + [0.1, 1.5])[:2]
    C = np.array(Image.open(cap).convert("RGB")).astype(np.float32)
    O = Image.open(src).convert("RGBA")
    if os.environ.get("BOX"):
        x, y, w, h = map(int, os.environ["BOX"].split(","))
        v, s = 1.0, w / O.width
    else:
        v, (s, _, _, _) = search(C, O, np.geomspace(lo, hi, 40), 4)
        if max(O.size) * s < 900:
            v, (s, (x, y), w, h) = search(C, O, np.geomspace(s / 1.08, s * 1.08, 9), 1)
        else:
            _, (s, (x, y), w, h) = search(C, O, [s], 4)
    print(f"score={v:.3f} scale={s:.3f} box=({x},{y},{w},{h})" + ("  LOW SCORE: check the box or pass BOX=" if v < 0.9 else ""))
    Cu = C.astype(np.uint8).copy()
    t = np.array(O.resize((w, h), Image.LANCZOS))
    N = Image.open(ours).convert("RGBA").resize((w, h), Image.LANCZOS)
    if "--full" in argv:
        keep = (np.abs(Cu[y:y + h, x:x + w].astype(int) - t[..., :3].astype(int)).sum(2) < 40) & (t[..., 3] > 0)
        Cu[y:y + h, x:x + w][keep] = np.array(N)[..., :3][keep]
    else:
        mask = np.zeros(Cu.shape[:2], np.uint8)
        mask[y:y + h, x:x + w] = (t[..., 3] > 20) * 255
        mask = cv2.dilate(mask, np.ones((11, 11) if os.environ.get("FILL") else (5, 5), np.uint8))
        if os.environ.get("FILL"):
            y0, x0 = max(0, y - 30), max(0, x - 30)
            reg, mm = Cu[y0:y + h + 30, x0:x + w + 30], mask[y0:y + h + 30, x0:x + w + 30] == 0
            Cu[mask > 0] = np.median(reg[mm], axis=0)
        else:
            Cu = cv2.inpaint(Cu, mask, 7, cv2.INPAINT_TELEA)
        im = Image.fromarray(Cu).convert("RGBA")
        im.alpha_composite(N, (x, y))
        Cu = np.array(im.convert("RGB"))
    L, R = Image.fromarray(C.astype(np.uint8)), Image.fromarray(Cu)
    pad, cx, cy = max(w, h) * 1.5, x + w / 2, y + h / 2
    box = tuple(int(q) for q in (max(0, cx - pad), max(0, cy - pad), min(C.shape[1], cx + pad), min(C.shape[0], cy + pad)))
    zl, zr = L.crop(box), R.crop(box)
    z = 700 / zl.height
    zl, zr = zl.resize((round(zl.width * z), 700)), zr.resize((round(zr.width * z), 700))
    fw = round(L.width * 700 / L.height)
    fl, fr = L.resize((fw, 700)), R.resize((fw, 700))
    sheet = Image.new("RGB", (fw * 2 + zl.width * 2 + 50, 700), "white")
    xx = 0
    for p in (fl, zl, zr, fr):
        sheet.paste(p, (xx, 0))
        xx += p.width + (30 if p is zl else 10)
    sheet.save(out, quality=90)


if __name__ == "__main__":
    main(sys.argv)
