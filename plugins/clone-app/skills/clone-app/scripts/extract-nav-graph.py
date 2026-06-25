#!/usr/bin/env python3
"""Build a navigation graph from a decompiled APK.

Primary source: res/**/navigation/*.xml (Jetpack Navigation) — fragment/activity/
dialog nodes, <action app:destination> edges. Secondary: Compose NavHost
composable() routes + navigate() calls grepped from .kt sources. Stdlib-only.
Emits nav-graph.json on stdout (or --out FILE).
"""
import os, re, json, glob, argparse
import xml.etree.ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"
APP = "{http://schemas.android.com/apk/res-auto}"

def _clean(s):
    return (s or "").replace("@+id/", "").replace("@id/", "")

def _nav_xml(root):
    nodes, edges = [], []
    for f in glob.glob(os.path.join(root, "**", "navigation", "*.xml"), recursive=True):
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            continue
        rel = os.path.relpath(f, root)
        for el in tree.getroot().iter():
            tag = el.tag.split("}")[-1]
            if tag not in ("fragment", "activity", "dialog"):
                continue
            nid = _clean(el.get(ANDROID + "id"))
            if not nid:
                continue
            nodes.append({"id": nid, "label": el.get(ANDROID + "name", ""),
                          "kind": tag, "source": rel})
            for child in list(el):
                if child.tag.split("}")[-1] == "action":
                    dest = _clean(child.get(APP + "destination"))
                    if dest:
                        edges.append({"from": nid, "to": dest,
                                      "trigger": _clean(child.get(ANDROID + "id")),
                                      "source": rel})
    return nodes, edges

def _compose(root):
    nodes, edges = [], []
    comp_pat = re.compile(r'composable\(\s*["\']([^"\']+)["\']')
    nav_pat = re.compile(r'navigate\(\s*["\']([^"\']+)["\']')
    for dp, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".kt"):
                continue
            path = os.path.join(dp, fn)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "NavHost" not in text:
                continue
            rel = os.path.relpath(path, root)
            for m in comp_pat.finditer(text):
                nodes.append({"id": m.group(1), "label": m.group(1),
                              "kind": "composable", "source": rel})
            for m in nav_pat.finditer(text):
                edges.append({"from": None, "to": m.group(1),
                              "trigger": "navigate", "source": rel})
    return nodes, edges

def extract(root):
    n1, e1 = _nav_xml(root)
    n2, e2 = _compose(root)
    fw = "navigation-xml" if n1 else ("compose" if n2 else "unknown")
    return {"root": root, "framework": fw, "nodes": n1 + n2, "edges": e1 + e2}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="decompile output root")
    ap.add_argument("--out")
    args = ap.parse_args()
    text = json.dumps(extract(args.root), indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)

if __name__ == "__main__":
    main()
