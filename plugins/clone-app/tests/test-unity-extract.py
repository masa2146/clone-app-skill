#!/usr/bin/env python3
"""Offline unit tests for unity-extract.py's pure helpers.

UnityPy is never imported: the script keeps every heavy dependency behind a
lazy import precisely so this suite runs on the stdlib alone.
"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "unity-extract.py")
FIX = os.path.join(HERE, "fixtures", "unity-sample")

spec = importlib.util.spec_from_file_location("unity_extract", SCRIPT)
ux = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ux)

fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


# --- split-file merge ordering ---------------------------------------------
groups = ux.split_groups([
    "sharedassets0.assets.split0", "sharedassets0.assets.split10",
    "sharedassets0.assets.split2", "level1.split1", "level1.split0",
    "globalgamemanagers", "level2",
])
check("split groups found", set(groups) == {"sharedassets0.assets", "level1"})
check("split order is numeric not lexicographic",
      groups["sharedassets0.assets"] == ["sharedassets0.assets.split0",
                                         "sharedassets0.assets.split2",
                                         "sharedassets0.assets.split10"])
check("non-split files excluded", "globalgamemanagers" not in groups)

with tempfile.TemporaryDirectory() as td:
    src = os.path.join(td, "src")
    os.makedirs(src)
    for i, chunk in enumerate([b"AAA", b"BBB", b"CCC"]):
        with open(os.path.join(src, f"data.assets.split{i}"), "wb") as f:
            f.write(chunk)
    with open(os.path.join(src, "plain"), "wb") as f:
        f.write(b"Z")
    dst = os.path.join(td, "merged")
    stats = ux.merge_sources([src], dst)
    with open(os.path.join(dst, "data.assets"), "rb") as f:
        merged = f.read()
    check("chunks concatenated in order", merged == b"AAABBBCCC")
    check("plain files carried over", os.path.exists(os.path.join(dst, "plain")))
    check("merge stats reported", stats["merged_split_groups"] == 1 and stats["linked"] == 1)
    check("a reused scratch reports the same stats (deterministic manifest)",
          ux.merge_sources([src], dst) == stats)

# --- broken-piece classification -------------------------------------------
check("whole mesh", ux.classify_mesh("stoneSquare1x1_geo") == "whole")
check("broken by keyword", ux.classify_mesh("StoneSquare_Broken_1x1_geo_03") == "broken")
check("broken by _piece", ux.classify_mesh("ColorBox_1X4_piece") == "broken")
check("broken by numeric geo suffix", ux.classify_mesh("Column_geo_02") == "broken")
check("empty name is whole", ux.classify_mesh("") == "whole")

# --- naming / collisions ----------------------------------------------------
check("safe_name strips separators", ux.safe_name("a/b:c") == "a_b_c")
check("safe_name falls back", ux.safe_name("   ") == "unnamed")
alloc = ux.NameAllocator()
p1 = alloc.path("/tmp", "Coin", ".png")
p2 = alloc.path("/tmp", "Coin", ".png")
check("collisions get a suffix", p1 != p2 and p2.endswith("Coin_1.png"))

# --- texture format lossiness ----------------------------------------------
check("RGBA32 lossless", ux.texture_format_info(4) == ("RGBA32", True))
check("ASTC_6x6 lossy", ux.texture_format_info(50) == ("ASTC_6x6", False))
check("unknown format degrades safely", ux.texture_format_info(9999)[1] is False)

# --- font sniffing ----------------------------------------------------------
check("ttf magic", ux.font_extension(b"\x00\x01\x00\x00rest") == ".ttf")
check("otf magic", ux.font_extension(b"OTTOrest") == ".otf")
check("list of ints accepted", ux.font_extension([0, 1, 0, 0]) == ".ttf")
check("unknown magic", ux.font_extension(b"junk") == ".bin")

# --- external / builtin references -----------------------------------------
externals = ["globalgamemanagers.assets", "Library/unity default resources", "other.assets"]
check("local ref is None", ux.external_kind(0, externals) is None)
check("builtin primitive detected",
      ux.external_kind(2, externals) == "builtin:Library/unity default resources")
check("other external labelled", ux.external_kind(3, externals) == "external:other.assets")
check("out-of-range degrades", ux.external_kind(99, externals) == "external:unknown")

# --- shader origin ----------------------------------------------------------
check("commercial shader named",
      ux.shader_origin("Toony Colors Pro 2/Hybrid Shader 2")[0] == "commercial")
check("urp is builtin",
      ux.shader_origin("Universal Render Pipeline/Lit")[0] == "builtin")
check("game shader is custom", ux.shader_origin("GameShaders/UI/Coin")[0] == "custom")

# --- mtl emission -----------------------------------------------------------
mtl = ux.mtl_text("StoneSquare", {"_MainTex": "textures/stone.png",
                                  "_NormalTex": "textures/stone_n.png"},
                  colors={"_BaseColor": [1, 0.5, 0.25, 1]}, floats={"_Smoothness": 0.5})
check("mtl declares material", mtl.startswith("newmtl StoneSquare"))
check("mtl carries diffuse map", "map_Kd textures/stone.png" in mtl)
check("mtl carries bump map", "map_Bump textures/stone_n.png" in mtl)
check("mtl carries base colour", "Kd 1.0000 0.5000 0.2500" in mtl)

obj = ux.attach_material_to_obj("g mesh\nv 0 0 0\n", "StoneSquare.mtl", "StoneSquare")
check("obj gains mtllib", obj.startswith("mtllib StoneSquare.mtl\nusemtl StoneSquare\n"))
check("obj not double-linked",
      ux.attach_material_to_obj(obj, "x.mtl", "x") == obj)

# --- manifest never over-claims --------------------------------------------
m = ux.build_manifest("unity", 100, {"textures": 5, "meshes": 3}, notes=["n"])
check("extracted derived from by_type", m["assets"]["extracted"] == 8)
check("expected preserved", m["assets"]["expected"] == 100)
check("manifest shape matches coverage contract",
      set(m) >= {"engine", "assets", "mechanics", "notes"}
      and set(m["assets"]) == {"expected", "extracted", "by_type"})

# --- level analysis + A/B detection ----------------------------------------
with open(os.path.join(FIX, "level-001-a.json")) as f:
    la = json.load(f)
with open(os.path.join(FIX, "level-001-b.json")) as f:
    lb = json.load(f)
with open(os.path.join(FIX, "level-002.json")) as f:
    l2 = json.load(f)
levels = {1: [la, lb], 2: [l2]}

ab = ux.level_duplicate_report(levels)
check("duplicate id counted", ab["duplicate_ids"] == 1)
check("MoveCount diff detected", ab["differing_fields"].get("MoveCount") == 1)
check("entity-count diff detected", ab["differing_fields"].get("Entities_len") == 1)

an = ux.analyse_levels(levels)
check("level count", an["levels"] == 2)
check("distinct entities", an["distinct_entities"] == 3)
check("first-appearance curve", an["entity_first_level"]["StoneSquare_1"] == 2)
check("usage counted", an["entity_usage"]["IceSquare_1"] == 2)
check("numeric stats derived", an["numeric_stats"]["MoveCount"]["min"] == 12)
check("mechanic intro ordered",
      [m["family"] for m in an["mechanic_introduction_order"]][0] == "IceSquare")
check("schema keys captured", "MoveCount" in an["schema_keys"])

# --- geometry status --------------------------------------------------------
def agg(**kw):
    base = {"meshes": [], "broken_pieces": [], "external_meshes": [], "sprites": [],
            "scripts": [], "materials": {}, "colliders": [], "joints": [],
            "particles": [], "particle_owners": [], "renderers": []}
    base.update(kw)
    return base


check("extracted status", ux._geometry_status(agg(meshes=["m"])) == "extracted")
check("builtin status",
      ux._geometry_status(agg(external_meshes=["builtin:Library/unity default resources"]))
      == "builtin-primitive")
check("procedural status",
      ux._geometry_status(agg(scripts=["TubeMeshGenerator"])) == "procedural")
check("sprite status", ux._geometry_status(agg(sprites=["s"])) == "sprite-based")
check("empty status", ux._geometry_status(agg()) == "empty")
check("vfx prefab labelled particle-effect",
      ux._geometry_status(agg(particles=["a.json"],
                              renderers=["ParticleSystemRenderer"])) == "particle-effect")
check("mesh wins over particles",
      ux._geometry_status(agg(meshes=["m"], particles=["a.json"],
                              renderers=["MeshRenderer"])) == "extracted")

# --- pruning ----------------------------------------------------------------
kept, dropped = ux.prune_entities(
    {"Ball": agg(meshes=["m"]), "Image_Bg": agg(), "JamJar_1": agg(),
     "Rope": agg(scripts=["VerletRopeGenerator"])},
    named_by_levels={"JamJar_1"})
check("substantive kept", "Ball" in kept)
check("level-named kept even when empty", "JamJar_1" in kept)
check("procedural kept", "Rope" in kept)
check("empty UI dropped", "Image_Bg" in dropped and "Image_Bg" not in kept)

# --- streamed clip decoding -------------------------------------------------
import struct as _struct
blob = _struct.pack("<fI", 0.5, 1) + _struct.pack("<I", 7) + _struct.pack("<4f", 1, 2, 3, 4)
words = list(_struct.unpack(f"<{len(blob)//4}I", blob))
frames = ux.decode_streamed_clip(words)
check("streamed frame decoded", len(frames) == 1 and abs(frames[0]["time"] - 0.5) < 1e-6)
check("streamed curve coefficients", frames[0]["curves"][7] == [1.0, 2.0, 3.0, 4.0])
check("empty streamed clip is empty", ux.decode_streamed_clip([]) == [])

# --- 0.3: identity, per-sub-mesh materials, references -----------------------
alloc = ux.NameAllocator()
a1 = alloc.path("/tmp", "Sphere_1", ".obj")
a2 = alloc.path("/tmp", "sphere_1", ".obj")
check("allocator is case-insensitive (macOS overwrote Sphere_1 with sphere_1)",
      a1.lower() != a2.lower())

multi = "g Box\nv 0 0 0\nv 1 0 0\nv 0 1 0\ng Box_0\nf 1 2 3\ng Box_1\nf 1 3 2\n"
painted = ux.attach_material_to_obj(multi, "m.mtl", ["Wood", "Metal"])
check("each sub-mesh group gets its own usemtl in slot order",
      painted.split("\n")[:1] == ["mtllib m.mtl"]
      and "g Box_0\nusemtl Wood\nf 1 2 3" in painted and "g Box_1\nusemtl Metal\nf 1 3 2" in painted)
check("material check counts painted groups", ux.obj_material_check(painted) == (2, 2))
check("single top-level usemtl counts as under-painted",
      ux.obj_material_check("usemtl A\n" + multi) == (2, 1))
short = ux.attach_material_to_obj(multi, "m.mtl", ["Wood"])
check("a sub-mesh without a slot is marked, not painted (Unity does not draw it)",
      "g Box_1\n" + ux.NO_SLOT + "\nf 1 3 2" in short and short.count("usemtl ") == 1
      and ux.obj_material_check(short) == (2, 2))

vals = {"BallPrefab": {"ref": "sharedassets2.assets:38", "type": "GameObject", "name": "Ball"},
        "list": [{"ref": "a:1", "type": "Sprite", "name": "s"}], "n": 3}
refs = dict(ux._walk_refs(vals))
check("script references are found with their field path",
      refs.get("BallPrefab", {}).get("name") == "Ball" and "list[0]" in refs)

with tempfile.TemporaryDirectory() as t:
    aa = os.path.join(t, "pack", "assets", "aa", "Android")
    os.makedirs(aa)
    open(os.path.join(aa, "art_assets_all.bundle"), "w").close()
    open(os.path.join(aa, "catalog.json"), "w").close()
    found = ux.find_bundle_files([os.path.join(t, "pack")])
    check("addressables bundles under assets/aa are found",
          [os.path.basename(f) for f in found] == ["art_assets_all.bundle"])
    for abi in ("armeabi-v7a", "arm64-v8a"):
        d = os.path.join(t, "lib", abi)
        os.makedirs(d)
        open(os.path.join(d, "libil2cpp.so"), "w").close()
    md = os.path.join(t, "assets", "bin", "Data", "Managed", "Metadata")
    os.makedirs(md)
    open(os.path.join(md, "global-metadata.dat"), "w").close()
    lib, meta = ux.find_il2cpp([t])
    check("64-bit libil2cpp preferred", "arm64-v8a" in lib and meta.endswith("global-metadata.dat"))

check("pick keeps only the named fields",
      ux._pick({"m_Sprite": 1, "m_Color": 2, "junk": 3}, ["m_Sprite", "m_Color"]) == {"m_Sprite": 1, "m_Color": 2})

# --- world placement maths (cameras, lights, scene anchors) --------------------
q90y = (0.0, 0.7071068, 0.0, 0.7071068)
r = ux._qrot(q90y, (1.0, 0.0, 0.0))
check("90 deg about y turns +x into -z", abs(r[0]) < 1e-6 and abs(r[2] + 1) < 1e-6)
q180 = ux._qmul(q90y, q90y)
r2 = ux._qrot(q180, (1.0, 0.0, 0.0))
check("two 90 deg turns compose to 180", abs(r2[0] + 1) < 1e-6)
check("JSON never gets Infinity/NaN (a C# reader looped on them)",
      ux._finite({"breakForce": float("inf"), "x": [float("nan"), 1.0]}) ==
      {"breakForce": "Infinity", "x": ["NaN", 1.0]})

sys.exit(1 if fails else 0)
