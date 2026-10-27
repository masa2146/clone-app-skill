#!/usr/bin/env python3
"""Self-check for a unity-extract.py output (game-assets/). Stdlib only.

Every number here is a way the extraction used to be silently wrong. A game
project should run this on day 1: a red line means "do not build on this data
yet", instead of weeks later in game.

    python3 check-extraction.py <game-assets> [--json] [--expect answers.json]

Exit code: 0 all invariants hold · 1 at least one failed · 2 usage error.

`--expect` takes known answers for this game (kept outside the repo, they name
the game), e.g.
    {"references": [{"from_class": "Game.LauncherController", "field": "ProjectilePrefab",
                     "to_name": "Projectile"}],
     "rigidbodies": [{"id_from_reference": "Game.LauncherController.ProjectilePrefab",
                      "mass": 1.2}],
     "entity_nodes": [{"entity": "Lock", "node": "Shackle", "parent_name": "Lock"}]}
"""
import argparse
import glob
import json
import os
import sys


def _load(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _walk(tree):
    stack = [tree]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(n.get("children") or [])


def measure(root):
    m = {}
    man = _load(os.path.join(root, "manifest.json"), {}) or {}
    by_type = (man.get("assets") or {}).get("by_type") or {}
    errors = man.get("errors") or {}
    m["format"] = "v0.3" if "unity_type_counts" in man else "legacy"

    # 1. UI: does each Image know the sprite it draws, and each canvas its scaler?
    images = bound = sprite_set = cr_nodes = graphic_known = ui_nodes = 0
    canvases = with_scaler = 0
    for p in glob.glob(os.path.join(root, "ui", "*.json")):
        c = _load(p, {}) or {}
        canvases += 1
        with_scaler += bool(c.get("scaler"))
        for n in _walk(c.get("tree") or {}):
            ui_nodes += 1
            comps = n.get("components") or []
            ui = n.get("ui") or {}
            # a CanvasRenderer alone draws nothing (the Graphic was stripped or never
            # added); a drawn node is one that also carries a script or a SpriteRenderer
            if "CanvasRenderer" in comps and (any(c.startswith("MB:") for c in comps)
                                              or "SpriteRenderer" in comps):
                cr_nodes += 1
                if any(k in ("Image", "RawImage", "TextMeshProUGUI", "TextMeshPro", "Text",
                             "SpriteRenderer") or k.startswith("Graphic:") for k in ui):
                    graphic_known += 1
            if "MB:Image" in comps or "Image" in ui:
                images += 1
                spr = (ui.get("Image") or {}).get("m_Sprite")
                if spr is not None:
                    sprite_set += 1
                    bound += bool(spr.get("ref"))
    m.update(ui_canvases=canvases, ui_canvases_with_scaler=with_scaler, ui_nodes=ui_nodes,
             ui_drawn_nodes=cr_nodes, ui_drawn_nodes_known=graphic_known,
             ui_image_nodes=images, ui_image_sprite_set=sprite_set, ui_image_sprite_bound=bound)

    # 2. particles cut short with "…"
    parts = glob.glob(os.path.join(root, "particles", "*.json"))
    cut = 0
    for p in parts:
        try:
            with open(p) as f:
                cut += "…" in f.read()
        except OSError:
            pass
    m.update(particle_files=len(parts), particle_files_cut=cut)

    # 3. records lost to name collisions
    mats = _load(os.path.join(root, "materials.json"), {}) or {}
    m["materials_read"] = int(by_type.get("materials", 0))
    m["materials_kept"] = len(mats)
    mesh_files = glob.glob(os.path.join(root, "meshes", "*.obj"))
    m["meshes_read"] = int(by_type.get("meshes", 0))
    m["meshes_on_disk"] = len(mesh_files)
    phys = _load(os.path.join(root, "physics.json"), {}) or {}
    rbs = phys.get("rigidbodies")
    m["rigidbodies_kept"] = len(rbs or [])
    m["rigidbodies_keyed_by_name"] = isinstance(rbs, dict)   # legacy: one record per name

    # 4. OBJ sub-meshes painted with their own material
    objs = unpainted = 0
    for p in glob.glob(os.path.join(root, "entities", "*", "*.obj")) + \
            glob.glob(os.path.join(root, "entities", "*", "broken", "*.obj")):
        groups = usemtl = 0
        in_faces = False
        try:
            with open(p) as f:
                for line in f:
                    if line.startswith("g "):
                        in_faces = False
                    elif line.startswith("f ") and not in_faces:
                        in_faces, groups = True, groups + 1
                    elif line.startswith("usemtl ") or line.startswith("# no material slot"):
                        usemtl += 1
        except OSError:
            continue
        objs += 1
        unpainted += usemtl < groups
    m.update(entity_objs=objs, entity_objs_unpainted=unpainted)

    # 5. hierarchy: parent known by id/path, back-link checked, nothing cut
    nodes = with_path = 0
    for p in glob.glob(os.path.join(root, "entities", "*", "entity.json")):
        for n in (_load(p, {}) or {}).get("nodes") or []:
            nodes += 1
            with_path += bool(n.get("path") and n.get("id"))
    m.update(entity_nodes=nodes, entity_nodes_with_path=with_path,
             father_mismatch=int(errors.get("tree:father-mismatch", 0)),
             tree_cut=sum(int(errors.get(k, 0)) for k in ("ui:tree-cut", "scene:tree-cut",
                                                         "entity:node-cap")),
             dump_cut=int(errors.get("dump:depth-cut", 0)) + int(errors.get("dump:list-cut", 0)))

    # 6. sources loaded, scripts decoded
    src = man.get("sources") or {}
    m["bundles_found"] = src.get("bundles_found")
    m["bundles_loaded"] = src.get("bundles_loaded")
    mb = man.get("monobehaviours") or {}
    m["monobehaviours"] = mb.get("total", (man.get("unity_type_counts") or {}).get("MonoBehaviour"))
    m["monobehaviours_decoded"] = mb.get("values_complete", 0)
    return m


# (name, failed?, explanation) — evaluated on the measured numbers
def invariants(m):
    legacy = m["format"] == "legacy"
    checks = [
        ("UI images bound to their real sprite",
         legacy or m["ui_image_sprite_bound"] < m["ui_image_sprite_set"],
         "not extracted — sprites are name guesses" if legacy else
         f"{m['ui_image_sprite_bound']}/{m['ui_image_sprite_set']} images know their sprite"),
        ("drawn UI nodes know what they draw",
         m["ui_drawn_nodes"] and m["ui_drawn_nodes_known"] < 0.9 * m["ui_drawn_nodes"],
         f"{m['ui_drawn_nodes_known']}/{m['ui_drawn_nodes']} CanvasRenderer nodes decoded"),
        ("root canvases carry their CanvasScaler",
         m["ui_canvases"] and m["ui_canvases_with_scaler"] == 0,
         f"{m['ui_canvases_with_scaler']}/{m['ui_canvases']} canvases"),
        ("particle files complete (no '…')", m["particle_files_cut"] > 0,
         f"{m['particle_files_cut']}/{m['particle_files']} cut"),
        ("no material lost to a name collision", m["materials_kept"] < m["materials_read"],
         f"{m['materials_kept']}/{m['materials_read']} kept"),
        ("no mesh file overwritten", m["meshes_on_disk"] < m["meshes_read"],
         f"{m['meshes_on_disk']}/{m['meshes_read']} on disk"),
        ("rigidbodies keyed by identity, not name", m["rigidbodies_keyed_by_name"],
         f"{m['rigidbodies_kept']} records" + (" (one per name)" if m["rigidbodies_keyed_by_name"] else "")),
        ("every OBJ sub-mesh has its own usemtl", m["entity_objs_unpainted"] > 0,
         f"{m['entity_objs_unpainted']}/{m['entity_objs']} OBJs under-painted"),
        ("entity nodes carry id + full path", m["entity_nodes"] and m["entity_nodes_with_path"] < m["entity_nodes"],
         f"{m['entity_nodes_with_path']}/{m['entity_nodes']} nodes"),
        ("children point back to their parent (m_Father)", legacy or m["father_mismatch"] > 0,
         f"{m['father_mismatch']} mismatches" + (" (not checked)" if legacy else "")),
        ("no tree cut by a depth/node limit", m["tree_cut"] > 0 or legacy,
         f"{m['tree_cut']} cuts" + (" (legacy output cuts at depth 5-6, uncounted)" if legacy else "")),
        ("asset bundles loaded", m["bundles_found"] is None or (m["bundles_loaded"] or 0) < (m["bundles_found"] or 0),
         f"{m['bundles_loaded']}/{m['bundles_found']}" if m["bundles_found"] is not None else "not scanned"),
        ("script field values decoded",
         legacy or (bool(m["monobehaviours"]) and m["monobehaviours_decoded"] < 0.8 * m["monobehaviours"]),
         "not decoded" if legacy else f"{m['monobehaviours_decoded']}/{m['monobehaviours']}"),
    ]
    return [(name, bool(bad), detail) for name, bad, detail in checks]


def check_expectations(root, expect):
    """Known answers for this game; each returns (label, ok, detail)."""
    out = []
    refs_path = os.path.join(root, "scripts", "references.tsv")
    refs = []
    if os.path.exists(refs_path):
        with open(refs_path) as f:
            head = f.readline().rstrip("\n").split("\t")
            refs = [dict(zip(head, l.rstrip("\n").split("\t"))) for l in f]
    phys = _load(os.path.join(root, "physics.json"), {}) or {}
    rbs = phys.get("rigidbodies") or []
    if isinstance(rbs, dict):
        rbs = [dict(v, gameObject=k) for k, v in rbs.items()]
    for e in expect.get("references") or []:
        hit = [r for r in refs if r.get("from_class") == e["from_class"]
               and r.get("field") == e["field"] and r.get("to_name") == e["to_name"]]
        out.append((f"{e['from_class']}.{e['field']} -> {e['to_name']}", bool(hit),
                    hit[0]["to_id"] if hit else "reference not in scripts/references.tsv"))
    for e in expect.get("rigidbodies") or []:
        cls, field = e["id_from_reference"].rsplit(".", 1)
        target = next((r["to_id"] for r in refs if r.get("from_class") == cls and r.get("field") == field), None)
        mass = next((rb.get("mass") for rb in rbs if target and rb.get("gameObject_id") == target), None)
        ok = mass is not None and abs(float(mass) - float(e["mass"])) < 1e-3
        out.append((f"mass of {e['id_from_reference']} = {e['mass']}", ok, f"found {mass}"))
    for e in expect.get("entity_nodes") or []:
        ent = _load(os.path.join(root, "entities", e["entity"], "entity.json"), {}) or {}
        node = next((n for n in ent.get("nodes") or [] if n.get("name") == e["node"]), None)
        got = node.get("parent_name") if node else None
        if node and got is None and isinstance(node.get("parent"), int) and node["parent"] >= 0:
            got = (ent["nodes"][node["parent"]] or {}).get("name")
        out.append((f"{e['entity']}: {e['node']} under {e['parent_name']}", got == e["parent_name"],
                    f"parent is {got}"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", help="game-assets output folder")
    ap.add_argument("--json", action="store_true", help="print the measured numbers as JSON")
    ap.add_argument("--expect", help="known-answers JSON for this game")
    a = ap.parse_args(argv)
    if not os.path.isfile(os.path.join(a.root, "manifest.json")):
        print(f"ERROR: {a.root} has no manifest.json — not a unity-extract output", file=sys.stderr)
        return 2
    m = measure(a.root)
    results = invariants(m)
    if a.expect:
        results += [(f"known answer: {l}", not ok, d)
                    for l, ok, d in check_expectations(a.root, _load(a.expect, {}) or {})]
    if a.json:
        print(json.dumps({"measured": m, "checks": [
            {"check": n, "failed": bad, "detail": d} for n, bad, d in results]}, indent=1))
    else:
        for name, bad, detail in results:
            print(f"{'FAIL' if bad else ' ok '}  {name}: {detail}")
    failed = sum(bad for _, bad, _ in results)
    if not a.json:
        print(f"\n{failed} of {len(results)} checks failed" if failed else f"\nall {len(results)} checks hold")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
