#!/usr/bin/env python3
"""What a correct Unity rebuild of an extraction must measure — computed from the
extracted files alone, independently of the importer. Stdlib only.

    python3 expected-import.py <game-assets> > expect.json

For every node of every entity: its parent id, local position/rotation/scale, and
for a mesh-bearing node the triangle count of each sub-mesh, the mesh's own
bounding box, and its box in the entity root's space (the transform chain applied
here, in Python). VerifyImport.cs measures the same on the built prefabs; a node
3 units off, a sub-mesh missing or a slot on the wrong region shows up as a
mismatch on that node.

Axis: UnityPy writes OBJ right-handed (x negated); Unity's importer negates it
back, so expected boxes use -x.
"""
import json
import math
import os
import sys


def obj_stats(path):
    """(triangles per face-bearing group, bbox of the vertices those faces use)."""
    verts, groups, cur, used = [], [], None, set()
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                verts.append((-float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("g "):
                cur = None
            elif line.startswith("f "):
                if cur is None:
                    groups.append(0)
                    cur = len(groups) - 1
                idx = [int(t.split("/")[0]) for t in line.split()[1:]]
                groups[cur] += max(0, len(idx) - 2)
                used.update(i - 1 if i > 0 else len(verts) + i for i in idx)
    pts = [verts[i] for i in used if 0 <= i < len(verts)]
    if not pts:
        return groups, None
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    return groups, lo + hi


def q_rot(q, v):
    x, y, z, w = q
    # v' = q v q*
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def to_parent(node, p):
    s = node.get("localScale") or [1, 1, 1]
    q = node.get("localRotation") or [0, 0, 0, 1]
    t = node.get("localPosition") or [0, 0, 0]
    r = q_rot(q, (p[0] * s[0], p[1] * s[1], p[2] * s[2]))
    return (r[0] + t[0], r[1] + t[1], r[2] + t[2])


def root_box(nodes, i, box):
    """AABB of `box` (node-local) expressed in the root node's own space."""
    corners = [(box[0 if a else 3], box[1 if b else 4], box[2 if c else 5])
               for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    cur = i
    while cur > 0:                       # stop at the root: its own TRS is excluded
        n = nodes[cur]
        corners = [to_parent(n, p) for p in corners]
        cur = n["parent"]
    lo = [min(p[k] for p in corners) for k in range(3)]
    hi = [max(p[k] for p in corners) for k in range(3)]
    return lo + hi


def main(root):
    edir = os.path.join(root, "entities")
    out = {"source": os.path.abspath(root), "entities": {}}
    for name in sorted(os.listdir(edir)):
        p = os.path.join(edir, name, "entity.json")
        if not os.path.isfile(p):
            continue
        ent = json.load(open(p))
        nodes = ent.get("nodes") or []
        rows = []
        for i, n in enumerate(nodes):
            row = {"id": n.get("id"), "name": n.get("name"),
                   "parent_id": nodes[n["parent"]]["id"] if n.get("parent", -1) >= 0 else None,
                   "localPosition": n.get("localPosition"), "localRotation": n.get("localRotation"),
                   "localScale": n.get("localScale"),
                   "material_ids": n.get("material_ids") or [],
                   "colliders": [c.get("type") for c in n.get("colliders") or []],
                   "mass": (n.get("rigidbody") or {}).get("mass"),
                   "sprite_file": n.get("sprite_file"), "builtin_mesh": n.get("builtin_mesh")}
            mf = n.get("mesh_file")
            if mf:
                for cand in (os.path.join(edir, name, mf), os.path.join(edir, name, "broken", mf)):
                    if os.path.isfile(cand):
                        tris, box = obj_stats(cand)
                        row["triangles"] = tris
                        if box:
                            row["mesh_box"] = box
                            row["root_box"] = root_box(nodes, i, box)
                        break
                else:
                    row["missing_mesh_file"] = mf
            rows.append(row)
        out["entities"][name] = {"entity": ent.get("entity"), "nodes": rows}
    json.dump(out, sys.stdout, indent=1)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
