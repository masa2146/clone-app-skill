#!/usr/bin/env python3
"""Self-check for scripts/art: grey-background cut (border + closed hole), board, in-frame rehearsal, gem.sh syntax."""
import os
import subprocess
import sys
import tempfile

try:
    import numpy as np
    import scipy  # noqa: F401
    from PIL import Image, ImageDraw
except ImportError:
    print("SKIP art tools (need numpy, scipy, Pillow)")
    sys.exit(0)

ART = os.path.join(os.path.dirname(__file__), "..", "skills", "clone-build", "scripts", "art")
sys.path.insert(0, ART)
fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    fails += not ok


d = tempfile.mkdtemp()
raw = Image.new("RGB", (400, 400), (128, 128, 128))
g = ImageDraw.Draw(raw)
g.ellipse((60, 60, 340, 340), fill=(220, 40, 40))
g.ellipse((160, 160, 240, 240), fill=(128, 128, 128))  # closed grey hole inside a red ring
raw.save(f"{d}/raw.png")

import fit  # noqa: E402

cut = fit.cut(Image.open(f"{d}/raw.png"))
a = np.asarray(cut.getchannel("A"))
check("border background cleared", a[5, 5] == 0)
check("closed grey hole cleared", a[200, 200] == 0)
check("subject kept", a[200, 90] == 255)
subprocess.run([sys.executable, f"{ART}/fit.py", f"{d}/raw.png", f"{d}/out.png", "128x64"], check=True, capture_output=True)
check("fit lands at the asked size", Image.open(f"{d}/out.png").size == (128, 64))

import pano  # noqa: E402

size = pano.board(f"{d}/board.png", "Test", [f"A · one|{d}/raw.png", f"B · two|{d}/raw.png"], H=200)
check("board holds both options", size[0] > 400 and os.path.exists(f"{d}/board.png"))

check("gem.sh parses", subprocess.run(["bash", "-n", f"{ART}/gem.sh"]).returncode == 0)

try:
    import cv2  # noqa: F401
except ImportError:
    print("SKIP ctx.py (no opencv)")
else:
    cap = Image.new("RGB", (600, 900), (30, 90, 160))
    spr = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spr)  # textured, so the scale is not ambiguous (a flat square matches at any smaller size)
    sd.ellipse((2, 2, 78, 78), fill=(250, 200, 20, 255))
    sd.rectangle((20, 30, 60, 42), fill=(200, 30, 120, 255))
    sd.ellipse((30, 52, 50, 72), fill=(20, 160, 60, 255))
    cap.paste(spr, (300, 400), spr)
    cap.save(f"{d}/cap.png"); spr.save(f"{d}/spr.png"); cut.save(f"{d}/ours.png")
    r = subprocess.run([sys.executable, f"{ART}/ctx.py", f"{d}/spr.png", f"{d}/cap.png", f"{d}/ours.png", f"{d}/ctx.jpg", "0.5", "2"],
                       capture_output=True, text=True)
    import re
    m = re.search(r"box=\((\d+),(\d+),(\d+),(\d+)\)", r.stdout)
    x, y, w, h = map(int, m.groups()) if m else (0, 0, 0, 0)
    check("ctx finds the sprite box", abs(x - 300) <= 3 and abs(y - 400) <= 3 and abs(w - 80) <= 4 and os.path.exists(f"{d}/ctx.jpg"))

sys.exit(1 if fails else 0)
