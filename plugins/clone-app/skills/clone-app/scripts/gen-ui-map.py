#!/usr/bin/env python3
"""Generate the UI usage map: where each element sits on screen and what it is for.

    python3 gen-ui-map.py <extracted-dir> --out <docs-dir>

Answers the question the asset catalog cannot:
    "the X in the top-right of a modal — which sprite is it, what is it for?"

Emits:
    UI-ROLE-GUIDE.md       recurring element roles: what/where/which sprites   <- read this first
    UI-ELEMENT-INDEX.tsv   greppable: canvas, node path, zone, size, sprite candidates

A per-canvas tree is NOT emitted as a second file — it is one awk line off the
index, and a generated file that only re-renders another generated file is a file
that goes stale. The recipe is printed in UI-ROLE-GUIDE.md.

Since clone-app 0.3 the extraction decodes uGUI script values, so each node's
`sprite` is the sprite its Image really draws (fact), its size is the resolved
rect (not the raw sizeDelta, which is a margin on stretched axes), its zone comes
from the absolute centre (not the anchors), and `px` is the on-screen box at the
target resolution through the canvas' CanvasScaler. `sprite_candidates` (a ranked
name-token guess) is only filled where no binding exists — legacy extractions,
or nodes without an Image.
"""

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

STOP = {"image", "bg", "parent", "content", "pivot", "root", "container",
        "group", "holder", "obj", "go", "new", "the", "view", "panel"}


# --------------------------------------------------------------------------- #

def find_game_dir(extracted):
    for cand in (os.path.join(extracted, "game-assets"),
                 os.path.join(extracted, "game-assets-legacy", "assets")):
        if os.path.isdir(cand):
            return cand
    sys.exit(f"no game-assets under {extracted}")


def toks(s):
    out = []
    for p in re.split(r"[^A-Za-z0-9]+", s):
        for piece in re.findall(r"[A-Z]?[a-z]+|\d+|[A-Z]+(?![a-z])", p):
            t = piece.lower()
            if len(t) > 2 and not t.isdigit():
                out.append(t)
    return out


def zone_of(rect):
    """Screen zone from the anchor pair. This part is fact, not inference."""
    if not rect:
        return "?"
    a0 = rect.get("anchorMin") or [0, 0]
    a1 = rect.get("anchorMax") or [0, 0]
    sx = abs(a1[0] - a0[0]) > 0.01
    sy = abs(a1[1] - a0[1]) > 0.01
    if sx and sy:
        return "full-stretch"
    cx = (a0[0] + a1[0]) / 2.0
    cy = (a0[1] + a1[1]) / 2.0
    hx = "left" if cx < 0.34 else ("right" if cx > 0.66 else "center")
    vy = "bottom" if cy < 0.34 else ("top" if cy > 0.66 else "middle")
    if sx:
        return f"stretch-x @{vy}"
    if sy:
        return f"stretch-y @{hx}"
    if hx == "center" and vy == "middle":
        return "center"
    return f"{vy}-{hx}"


def size_of(rect):
    if not rect:
        return ""
    sd = rect.get("sizeDelta") or [0, 0]
    if sd[0] or sd[1]:
        return f"{sd[0]:g}x{sd[1]:g}"
    return "(stretched)"


# --------------------------------------------------------------------------- #

def load_sprites(game_dir):
    d = os.path.join(game_dir, "sprites")
    if not os.path.isdir(d):
        return []
    return [os.path.splitext(f)[0] for f in sorted(os.listdir(d))
            if f.lower().endswith(".png")]


def match_sprites(node_name, sprite_toks, limit=4):
    nt = set(toks(node_name)) - STOP
    if not nt:
        return []
    scored = []
    for name, st in sprite_toks:
        ov = nt & st
        if not ov:
            continue
        score = len(ov) / max(1, len(nt | st) ** 0.5)
        scored.append((score, len(ov), name))
    scored.sort(reverse=True)
    return [n for _, _, n in scored[:limit]]


# --------------------------------------------------------------------------- #

def canvas_size(scaler, screen):
    """(canvas width, height in canvas units, scale) at `screen` through a
    CanvasScaler. Unity: ScaleWithScreenSize blends log2 of the two axis ratios
    by matchWidthOrHeight; Expand/Shrink take min/max; ConstantPixelSize uses
    scaleFactor. No scaler (legacy dump): the screen itself, scale 1."""
    sw, sh = screen
    if not scaler:
        return sw, sh, 1.0
    mode = scaler.get("m_UiScaleMode", 0)
    if mode == 1:
        ref = scaler.get("m_ReferenceResolution") or {}
        rw, rh = float(ref.get("x") or sw), float(ref.get("y") or sh)
        match_mode = scaler.get("m_ScreenMatchMode", 0)
        if match_mode == 1:
            k = min(sw / rw, sh / rh)
        elif match_mode == 2:
            k = max(sw / rw, sh / rh)
        else:
            m = float(scaler.get("m_MatchWidthOrHeight") or 0)
            k = 2 ** ((1 - m) * math.log2(sw / rw) + m * math.log2(sh / rh))
    else:
        k = float(scaler.get("m_ScaleFactor") or 1.0)
    return sw / k, sh / k, k


def _affine(frame):
    """A frame is (a, b, c, d, tx, ty, x0, y0, x1, y1): the parent's local -> canvas
    map X = a*x + c*y + tx, Y = b*x + d*y + ty, plus the parent's local rect.
    The 8-tuple form (ox, oy, kx, ky, x0, y0, x1, y1) is an unrotated frame."""
    if len(frame) == 8:
        ox, oy, kx, ky, x0, y0, x1, y1 = frame
        return (kx, 0.0, 0.0, ky, ox, oy, x0, y0, x1, y1)
    return frame


def place(node, frame):
    """Resolve a RectTransform inside its parent's local rect, rotation included.

    Returns the node's own frame and its axis-aligned box (x, y, w, h) in canvas
    units, y up. A rotated or mirrored node gets the box of its four corners."""
    a, b, c, d, tx, ty, px0, py0, px1, py1 = _affine(frame)
    r = node.get("rect")
    if not r:
        t = node.get("transform")
        if not t:
            return frame, None
        # plain Transform: placed by localPosition from the parent's pivot; its own
        # rect is a point, so children anchor there
        lp, sc = t.get("localPosition") or [0, 0, 0], t.get("localScale") or [1, 1, 1]
        q = t.get("localRotation") or [0, 0, 0, 1]
        th = 2 * math.atan2(q[2], q[3]) if len(q) >= 4 else 0.0
        cs, sn = math.cos(th), math.sin(th)
        la, lb, lc, ld = cs * sc[0], sn * sc[0], -sn * sc[1], cs * sc[1]
        return (a * la + c * lb, b * la + d * lb, a * lc + c * ld, b * lc + d * ld,
                a * lp[0] + c * lp[1] + tx, b * lp[0] + d * lp[1] + ty, 0.0, 0.0, 0.0, 0.0), None
    a0, a1 = r.get("anchorMin") or [0.5, 0.5], r.get("anchorMax") or [0.5, 0.5]
    pv, ap = r.get("pivot") or [0.5, 0.5], r.get("anchoredPosition") or [0, 0]
    sd, sc = r.get("sizeDelta") or [0, 0], r.get("localScale") or [1, 1, 1]
    q = r.get("localRotation") or [0, 0, 0, 1]
    ax0, ax1 = px0 + a0[0] * (px1 - px0), px0 + a1[0] * (px1 - px0)
    ay0, ay1 = py0 + a0[1] * (py1 - py0), py0 + a1[1] * (py1 - py0)
    w, h = (ax1 - ax0) + sd[0], (ay1 - ay0) + sd[1]
    pivx = ax0 + (ax1 - ax0) * pv[0] + ap[0]
    pivy = ay0 + (ay1 - ay0) * pv[1] + ap[1]
    theta = 2 * math.atan2(q[2], q[3]) if len(q) >= 4 else 0.0     # rotation about z
    cs, sn = math.cos(theta), math.sin(theta)
    sx, sy = (sc[0] if len(sc) > 0 else 1), (sc[1] if len(sc) > 1 else 1)
    # child local -> parent local: T(piv) R(theta) S(sx, sy); then the parent's map
    la, lb, lc, ld = cs * sx, sn * sx, -sn * sy, cs * sy
    na, nb = a * la + c * lb, b * la + d * lb
    nc, nd = a * lc + c * ld, b * lc + d * ld
    ntx, nty = a * pivx + c * pivy + tx, b * pivx + d * pivy + ty
    lx0, ly0 = -pv[0] * w, -pv[1] * h
    own = (na, nb, nc, nd, ntx, nty, lx0, ly0, lx0 + w, ly0 + h)
    xs, ys = [], []
    for x in (lx0, lx0 + w):
        for y in (ly0, ly0 + h):
            xs.append(na * x + nc * y + ntx)
            ys.append(nb * x + nd * y + nty)
    box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    return own, box


def zone_abs(box, cw, ch):
    if not box:
        return "?"
    cx, cy = (box[0] + box[2] / 2) / cw, (box[1] + box[3] / 2) / ch
    if box[2] >= 0.9 * cw and box[3] >= 0.9 * ch:
        return "full-screen"
    hx = "left" if cx < 0.34 else ("right" if cx > 0.66 else "center")
    vy = "bottom" if cy < 0.34 else ("top" if cy > 0.66 else "middle")
    return "center" if (hx, vy) == ("center", "middle") else f"{vy}-{hx}"


def walk(node, path, depth, out, frame=None, geo=None, sprites=None):
    """Flatten a canvas tree. With `geo` (canvas w/h + px factor) every node gets
    its absolute box; with decoded `ui` values, its bound sprite and text."""
    rect = node.get("rect")
    own, box = (frame, None)
    if geo and frame is not None:
        own, box = place(node, frame) if depth else (frame, (0, 0, geo["cw"], geo["ch"]))
    ui = node.get("ui") or {}
    img = ui.get("Image") or {}
    spr = img.get("m_Sprite") or {}
    meta = (sprites or {}).get(spr.get("ref")) if spr.get("ref") else None
    tmp = ui.get("TextMeshProUGUI") or ui.get("TextMeshPro") or {}
    row = {
        "name": node.get("name", "?"),
        "id": node.get("id", ""),
        "path": path,
        "depth": depth,
        "zone": zone_abs(box, geo["cw"], geo["ch"]) if box and geo else zone_of(rect),
        "size": f"{box[2]:.0f}x{box[3]:.0f}" if box else size_of(rect),
        "px": "",
        "scale": "",
        "components": node.get("components", []),
        "sprite": spr.get("name") or "",
        "sprite_file": meta["file"] if meta else "",
        "image_type": {0: "simple", 1: "sliced", 2: "tiled", 3: "filled"}.get(img.get("m_Type"), "")
                      if img else "",
        "painted_px": "",
        "text": (tmp.get("m_text") or (ui.get("Text") or {}).get("m_Text") or "").replace("\n", " ")[:80],
        "font_size": tmp.get("m_fontSize", ""),
    }
    if box and geo:
        f = geo["px"]
        x, y_top = box[0] * f, (geo["ch"] - box[1] - box[3]) * f
        row["px"] = f"{x:.0f},{y_top:.0f},{box[2] * f:.0f}x{box[3] * f:.0f}"
        k = math.hypot(own[0], own[1]) if own and len(own) == 10 else (own[2] if own else 1)
        row["scale"] = f"{k:g}" if abs(k - 1) > 1e-3 else "1"
        # painted extent: a Simple image draws the sprite's alpha box scaled into
        # the rect — that, not the rect, is what a reference screenshot measures
        if meta and meta.get("alpha_bbox") and meta.get("size") and row["image_type"] in ("simple", ""):
            sw, sh = meta["size"]
            bx0, by0, bx1, by1 = meta["alpha_bbox"]
            row["painted_px"] = f"{box[2] * f * (bx1 - bx0) / sw:.0f}x{box[3] * f * (by1 - by0) / sh:.0f}"
    out.append(row)
    for ch in node.get("children", []) or []:
        walk(ch, f"{path}/{ch.get('name','?')}", depth + 1, out, own, geo, sprites)


def load_sprite_meta(game_dir):
    """sprite id -> {file, size, alpha_bbox} from sprites/sprite-meta.json."""
    meta = {}
    p = os.path.join(game_dir, "sprites", "sprite-meta.json")
    try:
        data = json.load(open(p))
    except Exception:
        return meta
    for fname, v in data.items():
        if v.get("id"):
            meta[v["id"]] = {"file": fname, "size": v.get("size"), "alpha_bbox": v.get("alpha_bbox")}
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extracted")
    ap.add_argument("--out", required=True)
    ap.add_argument("--project-name", default="project")
    ap.add_argument("--screen", default="1080x2400",
                    help="target screen WxH for the px column (default 1080x2400)")
    a = ap.parse_args()
    screen = tuple(float(v) for v in a.screen.lower().split("x"))

    game_dir = find_game_dir(a.extracted)
    ui_dir = os.path.join(game_dir, "ui")
    os.makedirs(a.out, exist_ok=True)

    if not os.path.isdir(ui_dir):
        p = os.path.join(a.out, "UI-ROLE-GUIDE.md")
        alt = os.path.join(game_dir, "scene-hierarchy.txt")
        open(p, "w").write(
            f"# UI Role Guide — {a.project_name}\n\n"
            "**This extraction has no `ui/` canvas dump.**\n\n"
            f"The screen hierarchy source for this project is "
            f"`{os.path.abspath(alt)}` — read that instead. "
            "Node names there carry the same semantics (`Close Button`, `Popup Bg`, "
            "`Header Frame`), but anchors and sizes are not recorded, so screen "
            "position must be read off the store screenshots.\n")
        print("no ui/ — wrote pointer only:", p)
        return

    sprites = load_sprites(game_dir)
    sprite_toks = [(s, set(toks(s)) - STOP) for s in sprites]
    sprite_meta = load_sprite_meta(game_dir)

    canvases = []
    for f in sorted(os.listdir(ui_dir)):
        if not f.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(ui_dir, f)))
        except Exception:
            continue
        nodes = []
        geo, frame = None, None
        if d.get("render_mode") != 2:            # world-space canvases have no screen box
            cw, ch, k = canvas_size(d.get("scaler"), screen)
            geo = {"cw": cw, "ch": ch, "px": screen[0] / cw, "scale": k}
            frame = (cw / 2, ch / 2, 1.0, 1.0, -cw / 2, -ch / 2, cw / 2, ch / 2)
        walk(d.get("tree", {}), d.get("tree", {}).get("name", "?"), 0, nodes, frame, geo, sprite_meta)
        canvases.append({
            "file": f,
            "geo": geo, "scaler": d.get("scaler"), "nested": d.get("nested"),
            "name": d.get("name", os.path.splitext(f)[0]),
            "sorting_order": d.get("sorting_order"),
            "nodes": nodes,
            "scripts": sorted({c for n in nodes for c in n["components"]
                               if c.startswith("MB:")}),
        })

    # ---------------- role guide -------------------------------------------- #
    role = defaultdict(lambda: {"n": 0, "zones": Counter(), "sizes": Counter(),
                                "canvases": set(), "sprites": Counter()})
    for c in canvases:
        for n in c["nodes"]:
            r = role[n["name"]]
            r["n"] += 1
            r["zones"][n["zone"]] += 1
            if n["size"]:
                r["sizes"][n["size"]] += 1
            if n["sprite"]:
                r["sprites"][n["sprite"]] += 1
            r["canvases"].add(c["name"])
    bound_total = sum(1 for c in canvases for n in c["nodes"] if n["sprite"])

    common = sorted(role.items(), key=lambda kv: -kv[1]["n"])
    L = [f"# UI Role Guide — {a.project_name}", "",
         "> **Read this before building any screen.** It answers *where does this",
         "> element sit and what is it for*, which the asset catalog cannot.", "",
         f"{len(canvases)} canvases · {sum(len(c['nodes']) for c in canvases)} nodes · "
         f"{len(sprites)} sprites", "",
         "## How to read a row", "",
         "- **zone** — from the node's absolute centre on the canvas. **Fact.**",
         "- **typical size** — the resolved rect in canvas units (stretched axes",
         "  included, local scale applied). **Fact.** UNITS.md converts to pixels.",
         ("- **sprite** — the sprite the Image really draws, decoded from the scene"
          " data. **Fact** (" + str(bound_total) + " nodes bound)." if bound_total else
          "- **sprite candidates** — matched by name-token overlap and ranked. **A"
          " guess**: this extraction has no decoded Image values. Open the PNG first."), "",
         "## Recurring elements", "",
         "| element | count | usual zone | typical size | " +
         ("sprite (bound) |" if bound_total else "sprite candidates |"),
         "|---|---|---|---|---|"]
    for name, r in common[:70]:
        if r["n"] < 3:
            continue
        z = r["zones"].most_common(1)[0][0]
        s = r["sizes"].most_common(1)[0][0] if r["sizes"] else "-"
        cands = [x for x, _ in r["sprites"].most_common(3)] or \
            ([] if bound_total else match_sprites(name, sprite_toks))
        L.append(f"| `{name}` | {r['n']} | {z} | {s} | " +
                 (", ".join(f"`{x}`" for x in cands) if cands else "—") + " |")

    # pick the close-family node that actually exists in THIS extraction
    close_name = None
    for cand, r in sorted(role.items(), key=lambda kv: -kv[1]["n"]):
        if re.search(r"close|dismiss|\bexit\b|\bquit\b", cand, re.I):
            close_name = cand
            break
    L += ["", f"## Worked example — {close_name or 'the close control'}", ""]
    cb = role.get(close_name) if close_name else None
    if cb:
        zz = ", ".join(f"{z} ({n})" for z, n in cb["zones"].most_common(4))
        ss = ", ".join(f"{s} ({n})" for s, n in cb["sizes"].most_common(3))
        L += [f"`{close_name}` appears in **{cb['n']} canvases**.", "",
              f"- **zones:** {zz}",
              f"- **sizes:** {ss}",
              ("- **bound sprite:** " + (", ".join(f"`{x}` ({n})" for x, n in cb["sprites"].most_common(3)) or "—")
               if bound_total else
               "- **sprite candidates:** " +
               (", ".join(f"`{x}`" for x in match_sprites(close_name, sprite_toks)) or "—")),
              "- **canvases:** " + ", ".join(f"`{c}`" for c in sorted(cb["canvases"])[:10]) +
              (" …" if len(cb["canvases"]) > 10 else ""),
              "",
              "Close-family sprites in this extraction:", "", "```",
              "\n".join(x for x in sprites
                        if re.search(r"close|cross|dismiss|^x_|_x$", x, re.I))[:1200] or "(none)",
              "```", "",
              "So: a modal's close control is a node named "
              f"`{close_name}`, sitting at the zone above, " +
              ("drawing the bound sprite above (recovered from the scene data)."
               if bound_total else
               "and its art is one of the sprites listed. Open the PNG before choosing — "
               "the sprite link is a name match, not a recovered binding."),
              "",
              "Sibling nodes on the same control (grep the index for the canvas to see the",
              "full group — a close button is often plate + icon + hitbox, not one sprite):",
              "", "```bash",
              f"grep -P '\\t{close_name}\\t' UI-ELEMENT-INDEX.tsv | cut -f1,2,3,4",
              "```"]
    else:
        L.append("_No close-family node found in this extraction._")

    L += ["", "## Rebuild one canvas' tree (from the index, no second file needed)", "",
          "```bash",
          "awk -F'\\t' -v c='Popup Canvas' '$1==c{printf \"%*s%s  [%s %s]\\n\", $5*2, \"\", $2, $3, $4}' \\",
          "  Docs/assets/UI-ELEMENT-INDEX.tsv",
          "```",
          "",
          "Columns: 1 canvas · 2 node · 3 zone · 4 size · 5 depth · 6 components ·",
          "7 sprite candidates · 8 full path.", "",
          "## Naming conventions in this extraction", "",
          "Node names are semantic and stable — grep them, do not invent screens:", ""]
    fam = Counter()
    for name, r in role.items():
        t = toks(name)
        if t:
            fam[t[-1]] += r["n"]
    L.append("| trailing token | occurrences | means |")
    L.append("|---|---|---|")
    MEAN = {"button": "an interactive control", "frame": "a 9-sliced border plate",
            "text": "a TMP label", "icon": "a small square glyph",
            "pivot": "an empty transform used as an animation origin",
            "hitbox": "an invisible raycast target — no art",
            "shadow": "a soft blob under an element",
            "arrow": "a directional pointer sprite",
            "image": "a generic sprite host", "area": "a layout region",
            "title": "a header label", "content": "a scroll/layout body"}
    for t, n in fam.most_common(18):
        L.append(f"| `*{t}` | {n} | {MEAN.get(t,'—')} |")

    open(os.path.join(a.out, "UI-ROLE-GUIDE.md"), "w").write("\n".join(L))

    # ---------------- element index ----------------------------------------- #
    p = os.path.join(a.out, "UI-ELEMENT-INDEX.tsv")
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["canvas", "node", "zone", "size", "depth",
                    "components", "sprite_candidates", "path",
                    "id", "sprite", "sprite_file", "image_type", "px_" + a.screen, "painted_px",
                    "scale", "text", "font_size"])
        for c in canvases:
            for n in c["nodes"]:
                w.writerow([c["name"], n["name"], n["zone"], n["size"], n["depth"],
                            ";".join(n["components"]),
                            "" if n["sprite"] else ";".join(match_sprites(n["name"], sprite_toks)),
                            n["path"], n["id"], n["sprite"], n["sprite_file"], n["image_type"],
                            n["px"], n["painted_px"], n["scale"], n["text"], n["font_size"]])
    write_units(a.out, canvases, a.screen, a.project_name)

    print(f"canvases={len(canvases)} nodes={sum(len(c['nodes']) for c in canvases)} "
          f"sprites={len(sprites)}")
    for f in ("UI-ROLE-GUIDE.md", "UI-ELEMENT-INDEX.tsv", "UNITS.md"):
        fp = os.path.join(a.out, f)
        print("  wrote", fp, f"({os.path.getsize(fp)}B)")


def write_units(out, canvases, screen, project):
    """UNITS.md: how many screen pixels one canvas unit is, per scaler."""
    L = [f"# UI units — {project}", "",
         f"Target screen **{screen}**. A reference number read off a canvas is in canvas",
         "units; multiply by the factor below to get pixels on that screen. Every row of",
         "UI-ELEMENT-INDEX.tsv already carries the converted box in its `px_` column.", "",
         "| canvas | scaler | canvas size (units) | 1 unit = px |", "|---|---|---|---|"]
    for c in canvases:
        g, sc = c.get("geo"), c.get("scaler") or {}
        if not g:
            L.append(f"| `{c['name']}` | world space | — | — |")
            continue
        ref = sc.get("m_ReferenceResolution") or {}
        desc = (f"scale with screen, ref {ref.get('x', 0):g}x{ref.get('y', 0):g}, "
                f"match {sc.get('m_MatchWidthOrHeight', 0):g}") if sc.get("m_UiScaleMode") == 1 else \
            ("constant pixel size" if sc else "none decoded (legacy: assumed 1:1)")
        L.append(f"| `{c['name']}`{' (nested)' if c.get('nested') else ''} | {desc} | "
                 f"{g['cw']:.1f} x {g['ch']:.1f} | {g['px']:.5f} |")
    with open(os.path.join(out, "UNITS.md"), "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
