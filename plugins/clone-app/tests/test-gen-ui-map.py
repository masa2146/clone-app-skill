#!/usr/bin/env python3
"""Offline tests for gen-ui-map.py's geometry: CanvasScaler -> canvas size, and
RectTransform resolution into absolute boxes (the numbers a screen rebuild uses)."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "gen_ui_map", os.path.join(HERE, "..", "skills", "clone-app", "scripts", "gen-ui-map.py"))
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)

fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


def close(a, b, eps=1e-3):
    return all(abs(x - y) < eps for x, y in zip(a, b))


scaler = {"m_UiScaleMode": 1, "m_ReferenceResolution": {"x": 1000, "y": 2000},
          "m_ScreenMatchMode": 0, "m_MatchWidthOrHeight": 1}
check("match height: canvas height = reference height",
      close(gm.canvas_size(scaler, (1080, 2400)), (900, 2000, 1.2)))
check("match width: canvas width = reference width",
      close(gm.canvas_size(dict(scaler, m_MatchWidthOrHeight=0), (1080, 2400))[:2], (1000, 2222.222)))
check("no scaler: screen pixels", gm.canvas_size(None, (1080, 2400)) == (1080, 2400, 1.0))

cw, ch = 900, 2000
root = (cw / 2, ch / 2, 1.0, 1.0, -cw / 2, -ch / 2, cw / 2, ch / 2)
top_right = {"rect": {"anchorMin": [1, 1], "anchorMax": [1, 1], "pivot": [1, 1],
                      "anchoredPosition": [-10, -20], "sizeDelta": [100, 50], "localScale": [1, 1, 1]}}
own, box = gm.place(top_right, root)
check("anchored top-right box", close(box, (790, 1930, 100, 50)))
check("top-right zone from absolute centre, not anchors", gm.zone_abs(box, cw, ch) == "top-right")

stretched = {"rect": {"anchorMin": [0, 0], "anchorMax": [1, 1], "pivot": [0.5, 0.5],
                      "anchoredPosition": [0, 0], "sizeDelta": [-40, -40], "localScale": [1, 1, 1]}}
_, sbox = gm.place(stretched, root)
check("stretched node: sizeDelta is a margin, size comes from the parent", close(sbox, (20, 20, 860, 1960)))

scaled_parent = {"rect": {"anchorMin": [0.5, 0.5], "anchorMax": [0.5, 0.5], "pivot": [0.5, 0.5],
                          "anchoredPosition": [0, 0], "sizeDelta": [110, 110], "localScale": [1.6, 1.6, 1]}}
pown, pbox = gm.place(scaled_parent, root)
check("localScale 1.6 grows the drawn box (110 -> 176)", close(pbox[2:], (176, 176)))
child = {"rect": {"anchorMin": [0, 0], "anchorMax": [1, 1], "pivot": [0.5, 0.5],
                  "anchoredPosition": [0, 0], "sizeDelta": [0, 0], "localScale": [1, 1, 1]}}
_, cbox = gm.place(child, pown)
check("child of a scaled parent inherits the scale", close(cbox[2:], (176, 176)))

rows = []
tree = {"name": "Canvas", "children": [dict(top_right, name="Close", components=["MB:Image"],
        ui={"Image": {"m_Sprite": {"ref": "f:1", "name": "close_x"}, "m_Type": 0}})]}
geo = {"cw": cw, "ch": ch, "px": 1.2}
gm.walk(tree, "Canvas", 0, rows, root, geo, {"f:1": {"file": "close_x.png", "size": [100, 50],
                                                    "alpha_bbox": [10, 5, 90, 45]}})
close_row = rows[1]
check("bound sprite reported as fact", close_row["sprite"] == "close_x" and close_row["sprite_file"] == "close_x.png")
check("px box on the 1080x2400 screen (top-left origin)", close_row["px"] == "948,24,120x60")
check("painted size = alpha box inside the rect", close_row["painted_px"] == "96x48")

sys.exit(1 if fails else 0)
