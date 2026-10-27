#!/usr/bin/env python3
"""What a rebuilt canvas must measure, computed in Python from the dump alone.

    python3 expected-ui.py <game-assets> <CanvasName> [--texts texts-tr.json] [--screen 1080x2400] > expect.json

For every node: its box on the canvas (canvas units, origin bottom-left, rotation
and scale chain applied — gen-ui-map.py's geometry), the sprite file its Image is
bound to, the text its label shows (localized when a texts map is given), and
whether it is active. ImportUI.VerifyBatch measures the same in Unity's own
layout engine; a wrong anchor, pivot, scale or binding fails on that node.
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gen_ui_map", os.path.join(HERE, "gen-ui-map.py"))
gm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gm)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("canvas")
    ap.add_argument("--texts")
    ap.add_argument("--screen", default="1080x2400")
    a = ap.parse_args(argv)
    screen = tuple(float(v) for v in a.screen.lower().split("x"))
    cv = json.load(open(os.path.join(a.root, "ui", a.canvas + ".json")))
    meta = gm.load_sprite_meta(a.root)
    texts = (json.load(open(a.texts)).get("texts") or {}) if a.texts else {}
    cw, ch, _ = gm.canvas_size(cv.get("scaler"), screen)
    root_frame = (cw / 2, ch / 2, 1.0, 1.0, -cw / 2, -ch / 2, cw / 2, ch / 2)
    out = []

    def visit(n, frame, path):
        own, box = gm.place(n, frame)
        row = {"id": n.get("id"), "path": path, "active_self": bool(n.get("active", True))}
        if box:
            row["box"] = [round(v, 3) for v in box]
        img = (n.get("ui") or {}).get("Image") or {}
        sref = (img.get("m_Sprite") or {}).get("ref")
        if sref and sref in meta:
            row["sprite_file"] = meta[sref]["file"]
        for key in ("TextMeshProUGUI", "TextMeshPro"):
            t = (n.get("ui") or {}).get(key)
            if t is not None:
                tid = next((s["id"] for s in n.get("scripts") or [] if (s.get("class") or "").startswith("TextMeshPro")), None)
                row["text"] = texts.get(tid, t.get("m_text") or "")
        out.append(row)
        for c in n.get("children") or []:
            visit(c, own, f"{path}/{c.get('name', '?')}")

    tree = cv["tree"]
    for c in tree.get("children") or []:
        visit(c, root_frame, f"{tree.get('name')}/{c.get('name', '?')}")
    json.dump({"canvas": a.canvas, "canvas_size": [cw, ch], "nodes": out}, sys.stdout, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
