#!/usr/bin/env python3
"""check-extraction.py must go red on each old failure mode and green on a sound
v0.3 output. Synthetic fixtures, stdlib only."""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "check_extraction", os.path.join(HERE, "..", "skills", "clone-app", "scripts", "check-extraction.py"))
ce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ce)

fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


def write(root, rel, data):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))


def build(root, good):
    write(root, "manifest.json", {
        "assets": {"by_type": {"materials": 2, "meshes": 1}},
        **({"unity_type_counts": {"MonoBehaviour": 2}, "errors": {},
            "sources": {"bundles_found": 1, "bundles_loaded": 1},
            "monobehaviours": {"total": 2, "values_complete": 2}} if good else {})})
    img = {"name": "Close", "components": ["RectTransform", "CanvasRenderer", "MB:Image"]}
    if good:
        img["ui"] = {"Image": {"m_Sprite": {"ref": "f:1", "type": "Sprite", "name": "x"}}}
    write(root, "ui/Canvas.json", {"scaler": {"m_UiScaleMode": 1} if good else None,
                                   "tree": {"name": "Canvas", "components": [], "children": [img]}})
    write(root, "particles/Boom.json", '{"UVModule": {"sprites": "%s"}}' % ("[]" if good else "…"))
    write(root, "materials.json", {"a:1": {"name": "M"}, "a:2": {"name": "M"}} if good else {"M": {}})
    write(root, "meshes/Box.obj", "g Box\n")
    write(root, "physics.json", {"rigidbodies": [] if good else {}})
    obj = "g Box\nv 0 0 0\ng Box_0\n" + ("usemtl A\n" if good else "") + "f 1 1 1\ng Box_1\n" + \
          ("usemtl B\n" if good else "") + "f 1 1 1\n"
    write(root, "entities/Box/Box.obj", ("" if good else "usemtl A\n") + obj)
    write(root, "entities/Box/entity.json", {"nodes": [
        {"name": "Box", "id": "a:9", "path": "Box"} if good else {"name": "Box", "parent": -1}]})


with tempfile.TemporaryDirectory() as t:
    old, new = os.path.join(t, "old"), os.path.join(t, "new")
    build(old, False)
    build(new, True)
    bad = {n for n, failed, _ in ce.invariants(ce.measure(old)) if failed}
    for name in ("UI images bound to their real sprite", "root canvases carry their CanvasScaler",
                 "particle files complete (no '…')", "no material lost to a name collision",
                 "rigidbodies keyed by identity, not name", "every OBJ sub-mesh has its own usemtl",
                 "entity nodes carry id + full path", "script field values decoded"):
        check(f"legacy output fails: {name}", name in bad)
    good_fail = [n for n, failed, _ in ce.invariants(ce.measure(new)) if failed]
    check("sound output passes every invariant", good_fail == [])
    check("exit code 1 on a red extraction", ce.main([old]) == 1)
    check("exit code 0 on a green extraction", ce.main([new]) == 0)
    check("usage error on a non-extraction folder", ce.main([t]) == 2)

sys.exit(1 if fails else 0)
