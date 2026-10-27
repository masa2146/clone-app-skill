#!/usr/bin/env python3
"""expected-import.py: the independent numbers VerifyImport.cs checks prefabs against."""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "expected_import", os.path.join(HERE, "..", "skills", "clone-app", "scripts", "expected-import.py"))
ei = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ei)
fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


def close(a, b):
    return all(abs(x - y) < 1e-6 for x, y in zip(a, b))


with tempfile.TemporaryDirectory() as t:
    obj = os.path.join(t, "box.obj")
    with open(obj, "w") as f:
        # x is written negated (right-handed): Unity-space x runs 0..1
        f.write("g box\nv 0 0 0\nv -1 0 0\nv 0 2 0\nv -1 2 3\nv -9 9 9\n"
                "g box_0\nf 1 2 3\ng box_1\nf 2 3 4\nf 1 2 4\n")
    tris, box = ei.obj_stats(obj)
    check("triangles per face-bearing group", tris == [1, 2])
    check("box uses only vertices the faces touch, x un-negated", close(box, [0, 0, 0, 1, 2, 3]))

    nodes = [{"parent": -1, "localPosition": [5, 5, 5], "localScale": [3, 3, 3]},          # root: excluded
             {"parent": 0, "localPosition": [1, 0, 0], "localScale": [2, 2, 2]},
             {"parent": 1, "localPosition": [0, 1, 0], "localRotation": [0, 0.7071068, 0, 0.7071068]}]
    rb = ei.root_box(nodes, 2, [0, 0, 0, 1, 2, 3])
    # node 2: rotate 90 deg about y: x->-z, z->x ; then +[0,1,0]; node 1: *2, +[1,0,0]
    check("root-space box applies the chain below the root, not the root itself",
          close(rb, [1, 2, -2, 7, 6, 0]))

sys.exit(1 if fails else 0)
