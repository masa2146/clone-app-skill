#!/usr/bin/env python3
"""Extract a design-token digest from a decompiled APK resource tree.

Reads res/values/{colors,dimens,styles,themes}.xml, the res/font/ dir, the
drawable*/mipmap* inventory, and counts res/layout/*.xml. Stdlib-only.

Emits a design-tokens.json object on stdout (or --out FILE) and, with --digest
FILE, a markdown design summary. Framework-aware: native apps have a rich XML
layer (confidence high); Compose keeps tokens in res/values but no layouts
(med); Flutter/React Native keep almost nothing in Android res (low) so the
caller leans on screenshots. Pass --framework to override the auto guess.
"""
import os, json, argparse, glob
import xml.etree.ElementTree as ET

def _find_res_dirs(root):
    """All res/ dirs under root that contain a values/ subdir (jadx puts these
    under <out>/resources/res; apktool under <out>/res — search either)."""
    hits = []
    for p in glob.glob(os.path.join(root, "**", "res"), recursive=True):
        if os.path.isdir(os.path.join(p, "values")) or glob.glob(os.path.join(p, "values*")):
            hits.append(p)
    return sorted(set(hits))

def _iter_value_files(res_dirs, basename):
    for res in res_dirs:
        for vdir in glob.glob(os.path.join(res, "values*")):
            f = os.path.join(vdir, basename)
            if os.path.isfile(f):
                yield f

def _parse_named(res_dirs, basename, tag):
    """Collect <tag name="X">value</tag> entries from every values*/basename."""
    out = {}
    for f in _iter_value_files(res_dirs, basename):
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            continue
        for el in tree.getroot().iter(tag):
            name = el.get("name")
            if name and (el.text is not None):
                out[name] = el.text.strip()
    return out

def _parse_themes(res_dirs):
    """First <style> whose name contains 'Theme' — parent + items + dark guess."""
    for base in ("themes.xml", "styles.xml"):
        for f in _iter_value_files(res_dirs, base):
            try:
                tree = ET.parse(f)
            except ET.ParseError:
                continue
            for st in tree.getroot().iter("style"):
                name = st.get("name", "")
                if "Theme" not in name:
                    continue
                parent = st.get("parent", "")
                items = {it.get("name"): (it.text or "").strip()
                         for it in st.iter("item") if it.get("name")}
                hay = (name + " " + parent).lower()
                is_dark = ("night" in hay) or ("dark" in hay)
                return {"name": name, "parent": parent, "items": items,
                        "is_dark": is_dark}
    return {}

def _font_files(res_dirs):
    fonts = []
    for res in res_dirs:
        for fdir in glob.glob(os.path.join(res, "font*")):
            for f in sorted(glob.glob(os.path.join(fdir, "*"))):
                fonts.append(os.path.basename(f))
    return sorted(set(fonts))

def _layout_files(res_dirs):
    files = []
    for res in res_dirs:
        for ldir in glob.glob(os.path.join(res, "layout*")):
            files += [os.path.basename(x) for x in glob.glob(os.path.join(ldir, "*.xml"))]
    return sorted(set(files))

def _drawable_count(res_dirs):
    n = 0
    for res in res_dirs:
        for ddir in glob.glob(os.path.join(res, "drawable*")) + glob.glob(os.path.join(res, "mipmap*")):
            n += len(glob.glob(os.path.join(ddir, "*")))
    return n

def _icon(res_dirs):
    for res in res_dirs:
        for ddir in sorted(glob.glob(os.path.join(res, "mipmap*")), reverse=True):
            hits = glob.glob(os.path.join(ddir, "ic_launcher*"))
            if hits:
                return os.path.relpath(sorted(hits)[0])
    return None

def _guess_framework(root):
    for _ in (1,):
        if glob.glob(os.path.join(root, "**", "libil2cpp.so"), recursive=True) or \
           glob.glob(os.path.join(root, "**", "libunity.so"), recursive=True):
            return "unity"
        if glob.glob(os.path.join(root, "**", "libflutter.so"), recursive=True) or \
           glob.glob(os.path.join(root, "**", "flutter_assets"), recursive=True):
            return "flutter"
        if glob.glob(os.path.join(root, "**", "index.android.bundle"), recursive=True):
            return "react-native"
    return "android"

# confidence per framework: native android = high, compose-ish (no layouts but
# res present) = med, flutter/rn/unity = low.
def _confidence(framework, layouts_count):
    if framework in ("flutter", "react-native", "unity"):
        return "low"
    if layouts_count == 0:
        return "med"
    return "high"

def extract(root, framework=None):
    res_dirs = _find_res_dirs(root)
    fw = framework or _guess_framework(root)
    layouts = _layout_files(res_dirs)
    conf = _confidence(fw, len(layouts))
    colors = _parse_named(res_dirs, "colors.xml", "color")
    dimens = _parse_named(res_dirs, "dimens.xml", "dimen")
    theme = _parse_themes(res_dirs)
    text_sizes = {k: v for k, v in dimens.items() if v.endswith("sp")}
    return {
        "package": None,
        "source": "apk-resources",
        "framework": fw,
        "colors":     {"values": colors, "confidence": conf},
        "dimens":     {"values": dimens, "confidence": conf},
        "typography": {"values": {"fonts": _font_files(res_dirs),
                                  "text_sizes": text_sizes}, "confidence": conf},
        "shapes":     {"values": {"corner_dimens":
                                  {k: v for k, v in dimens.items()
                                   if "corner" in k or "radius" in k}},
                       "confidence": conf},
        "theme":      {"values": theme, "confidence": conf},
        "icon":       {"values": {"path": _icon(res_dirs)}, "confidence": conf},
        "layouts":    {"values": {"count": len(layouts), "files": layouts},
                       "confidence": conf},
    }

def digest_md(d):
    L = [f"# Design Digest — {d.get('package') or '(unknown)'}",
         f"Framework: {d['framework']}  ·  source: {d['source']}", ""]
    L.append(f"## Colors ({d['colors']['confidence']})")
    for k, v in d["colors"]["values"].items():
        L.append(f"- `{k}` = {v}")
    L.append(f"\n## Dimens ({d['dimens']['confidence']})")
    for k, v in d["dimens"]["values"].items():
        L.append(f"- `{k}` = {v}")
    th = d["theme"]["values"]
    L.append(f"\n## Theme ({d['theme']['confidence']})")
    L.append(f"- name: {th.get('name')}  parent: {th.get('parent')}  dark: {th.get('is_dark')}")
    L.append(f"\n## Typography ({d['typography']['confidence']})")
    L.append(f"- fonts: {', '.join(d['typography']['values']['fonts']) or '(none in res)'}")
    L.append(f"\n## Layouts ({d['layouts']['confidence']})")
    L.append(f"- count: {d['layouts']['values']['count']}")
    L.append(f"\n## Icon\n- {d['icon']['values']['path']}")
    return "\n".join(L) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="decompile output root")
    ap.add_argument("--framework")
    ap.add_argument("--package")
    ap.add_argument("--out")
    ap.add_argument("--digest")
    args = ap.parse_args()
    d = extract(args.root, args.framework)
    if args.package:
        d["package"] = args.package
    text = json.dumps(d, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)
    if args.digest:
        with open(args.digest, "w") as f:
            f.write(digest_md(d))

if __name__ == "__main__":
    main()
