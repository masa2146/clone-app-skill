#!/usr/bin/env python3
"""Full, grouped, ready-to-use Unity asset extraction from an APK/XAPK.

Runs under the opt-in extraction venv (setup-extraction-venv.sh): UnityPy is
required, numpy+Pillow only for mesh previews. Every heavy import is lazy so the
pure helpers below stay importable — and unit-testable — with the stdlib alone.

Governing rule: **Unity engine types ship their type tree inside the serialized
file, so every field is readable. User types (MonoBehaviour / ScriptableObject)
are stripped in an IL2CPP release build — but their layout is still in
libil2cpp.so + global-metadata.dat, so the type trees are rebuilt from there
(TypeTreeGeneratorAPI) and script field values are decoded too.** What is truly
absent from the data files: shader HLSL and IL2CPP method bodies (logic).

Identity rule: every object is keyed by `<serialized file>:<path id>`. Names are
not unique, and every name-keyed join in the old output lost or swapped data.

Output layout is the contract in references/unity-asset-extraction-guide.md.
"""
import argparse
import collections
import json
import os
import re
import shutil
import struct
import sys
import zipfile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Unity TextureFormat enum -> (name, lossless?). Only the formats that actually
# turn up in shipped mobile builds; anything else is reported by its raw id.
TEXTURE_FORMATS = {
    1: ("Alpha8", True), 2: ("ARGB4444", False), 3: ("RGB24", True),
    4: ("RGBA32", True), 5: ("ARGB32", True), 7: ("RGB565", False),
    12: ("RGBA4444", False), 13: ("BGRA32", True),
    10: ("DXT1", False), 12000: ("DXT5", False),
    34: ("ETC_RGB4", False), 45: ("ETC2_RGB", False),
    46: ("ETC2_RGBA1", False), 47: ("ETC2_RGBA8", False),
    48: ("ASTC_4x4", False), 49: ("ASTC_5x5", False), 50: ("ASTC_6x6", False),
    51: ("ASTC_8x8", False), 52: ("ASTC_10x10", False), 53: ("ASTC_12x12", False),
    54: ("ASTC_HDR_4x4", False), 62: ("RG16", True), 63: ("R8", True),
}

# A mesh whose name matches this is a fracture/debris piece, not the whole object.
BROKEN_RE = re.compile(r"broken|_piece|_geo_\d+$|_shard|_cell(\.\d+)*$", re.I)
# A node is debris when an ancestor says so — structural, not a name guess.
FRACTURE_PARENT_RE = re.compile(r"break|broken|crack|debris|shatter|destruct", re.I)

# Gameplay nouns worth grouping even when the level data never names them —
# remote/CDN levels routinely hide Magnet/Portal/WreckingBall/Rope from the
# shipped level database.
ENTITY_HINT_RE = re.compile(
    r"cannon|launcher|paddle|projectile|magnet|wormhole|portal|pinata|"
    r"wrecking|\brope\b|barrage|hammer|\btnt\b|blocker|bouncer|obstacle|"
    r"\bball\b|bigball|bullet",
    re.I,
)

# Menu/HUD objects that share those nouns but are not gameplay entities. Names
# matching this are only kept when the level data itself names them.
UI_NOISE_RE = re.compile(
    r"^(image|text|txt|button|btn|canvas|panel|icon|bg|background|ps_|vfx_|"
    r"anim|mask|layout|scroll|slider|toggle|spacer)|"
    r"(view|controller|manager|screen|popup|tutorial|button|locked|"
    r"spawnpos|pos|ref|item|hit|animator|holder|root|parent|group|slot)$",
    re.I,
)

SAFE_RE = re.compile(r"[^\w\-.() ]")

# TextAssets that are level definitions. Numeric names are the most common
# convention; the prefixed forms cover the rest. A game that stores levels as
# ScriptableObjects instead is a genuine miss and is reported as such.
LEVEL_NAME_RE = re.compile(r"^(?:level|stage|map|puzzle|lvl|chapter)[\s_\-]*(\d+)$", re.I)

# Shader families we can name a source for, so the report can say buy-vs-reauthor.
KNOWN_SHADER_VENDORS = (
    ("Toony Colors Pro", "commercial", "Toony Colors Pro 2 (Unity Asset Store)"),
    ("Spine/", "commercial", "spine-unity runtime (Esoteric Software)"),
    ("TextMeshPro/", "builtin", "TextMeshPro (Unity package)"),
    ("Universal Render Pipeline/", "builtin", "URP (Unity package)"),
    ("Hidden/", "builtin", "Unity internal"),
    ("UI/", "builtin", "Unity UI (may be overridden — check pass count)"),
    ("Sprites/", "builtin", "Unity 2D"),
    ("Standard", "builtin", "Unity built-in"),
)


# ---------------------------------------------------------------------------
# Pure helpers — no UnityPy, unit-tested offline
# ---------------------------------------------------------------------------

def _finite(v):
    """JSON has no Infinity/NaN (a joint's breakForce is +inf); write them as
    strings so every reader — not only Python's — can parse the file."""
    if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
        return "NaN" if v != v else ("Infinity" if v > 0 else "-Infinity")
    if isinstance(v, dict):
        return {k: _finite(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_finite(x) for x in v]
    return v


def _dump_json(payload, f, **kw):
    json.dump(_finite(payload), f, allow_nan=False, **kw)


def safe_name(name, fallback="unnamed", limit=120):
    """Filesystem-safe asset name. Empty/whitespace names get the fallback."""
    n = SAFE_RE.sub("_", (name or "").strip())
    n = n.strip(". ")
    return (n or fallback)[:limit]


def split_groups(filenames):
    """Group `<base>.splitN` names -> {base: [names in numeric order]}.

    Unity chunks large serialized files; loading a chunk alone yields nothing,
    so the chunks must be concatenated in numeric (not lexicographic) order.
    """
    groups = collections.defaultdict(list)
    for f in filenames:
        m = re.match(r"^(.*)\.split(\d+)$", f)
        if m:
            groups[m.group(1)].append((int(m.group(2)), f))
    return {base: [n for _, n in sorted(parts)] for base, parts in groups.items()}


def level_index(stem):
    """Level number for a TextAsset name, or None if it is not level data."""
    if not stem:
        return None
    if stem.isdigit():
        return int(stem)
    m = LEVEL_NAME_RE.match(stem)
    return int(m.group(1)) if m else None


def classify_mesh(mesh_name):
    """'broken' for fracture debris, 'whole' otherwise."""
    return "broken" if BROKEN_RE.search(mesh_name or "") else "whole"


def texture_format_info(fmt):
    """(name, lossless) for a Unity TextureFormat id."""
    try:
        key = int(fmt)
    except (TypeError, ValueError):
        return (str(fmt), False)
    return TEXTURE_FORMATS.get(key, (f"unknown({key})", False))


def font_extension(data):
    """Sniff a font container by magic. Unity hands back raw TTF/OTF bytes."""
    head = bytes(data[:4]) if data else b""
    if head in (b"\x00\x01\x00\x00", b"true", b"ttcf"):
        return ".ttf"
    if head == b"OTTO":
        return ".otf"
    if head == b"wOFF":
        return ".woff"
    return ".bin"


def external_kind(file_id, externals):
    """Classify a PPtr that points outside this serialized file.

    m_FileID 0 is local; 1..n index `externals` (1-based). A reference into
    'Library/unity default resources' is a Unity built-in primitive — that is a
    *finding*, not an extraction failure, and must never be counted as missing.
    """
    if not file_id:
        return None
    try:
        name = externals[int(file_id) - 1]
    except (IndexError, TypeError, ValueError):
        return "external:unknown"
    low = str(name).lower()
    if "unity default resources" in low or "unity_builtin" in low:
        return f"builtin:{name}"
    return f"external:{name}"


def shader_origin(shader_name):
    """(origin, note) — builtin / commercial / custom, for buy-vs-reauthor."""
    n = shader_name or ""
    # Prefix match only: "GameShaders/UI/Coin" is a game shader, not Unity's "UI/".
    for prefix, origin, note in KNOWN_SHADER_VENDORS:
        if n.startswith(prefix):
            return origin, note
    return "custom", "no known source — re-author from the property table below"


def level_duplicate_report(levels):
    """levels: {level_id: [parsed dicts]} -> A/B variant findings.

    Two payloads under one id means the build ships parallel level ladders,
    which is a live A/B test and is invisible from anywhere else.
    """
    dupes, fields = {}, collections.Counter()
    for lid, variants in levels.items():
        if len(variants) < 2:
            continue
        a, b = variants[0], variants[1]
        diff = []
        for k in a:
            if k == "Entities":
                if len(a.get(k) or []) != len(b.get(k) or []):
                    diff.append("Entities_len")
                elif a.get(k) != b.get(k):
                    diff.append("Entities_content")
            elif a.get(k) != b.get(k):
                diff.append(k)
        if diff:
            dupes[lid] = diff
            fields.update(diff)
    return {"duplicate_ids": len(dupes), "differing_fields": dict(fields),
            "sample": dict(list(dupes.items())[:5])}


def mtl_text(material_name, textures, colors=None, floats=None):
    """Wavefront .mtl body. UnityPy's OBJ export writes no material link at all,
    so without this every extracted mesh imports untextured."""
    colors, floats = colors or {}, floats or {}
    base = colors.get("_BaseColor") or colors.get("_Color") or [1.0, 1.0, 1.0, 1.0]
    spec = colors.get("_SpecColor") or [0.2, 0.2, 0.2, 1.0]
    lines = [f"newmtl {safe_name(material_name, 'material')}",
             "Ka 0.200 0.200 0.200",
             "Kd %.4f %.4f %.4f" % tuple(float(c) for c in base[:3]),
             "Ks %.4f %.4f %.4f" % tuple(float(c) for c in spec[:3])]
    alpha = float(base[3]) if len(base) > 3 else 1.0
    lines.append("d %.4f" % alpha)
    smooth = floats.get("_Smoothness")
    if smooth is not None:
        lines.append("Ns %.2f" % (float(smooth) * 1000.0))
    for slot in ("_MainTex", "_BaseMap", "_MatCapTex", "_NormalTex", "_BumpMap"):
        f = textures.get(slot)
        if not f:
            continue
        if slot in ("_NormalTex", "_BumpMap"):
            lines.append(f"map_Bump {f}")
        elif not any(l.startswith("map_Kd") for l in lines):
            lines.append(f"map_Kd {f}")
    return "\n".join(lines) + "\n"


def attach_material_to_obj(obj_text, mtl_filename, material_names):
    """Insert mtllib + one usemtl per sub-mesh into an OBJ UnityPy exported without them.

    UnityPy writes `g <mesh>` (vertices only) and then one `g <mesh>_N` group per
    sub-mesh. Unity draws sub-mesh N with material slot N, so slot N's material goes
    in front of the N-th face-bearing group. A single `usemtl` at the top painted
    every region with slot 0 (a clone project had to patch around it in its own importer).
    A slot with no sub-mesh left is Unity re-drawing the last sub-mesh; a sub-mesh
    with no slot is not drawn at all, so it gets no usemtl."""
    if "mtllib" in obj_text:
        return obj_text
    if isinstance(material_names, str) or material_names is None:
        material_names = [material_names]
    lines = obj_text.split("\n")
    heads = [i for i, l in enumerate(lines) if l.startswith("g ")]
    bearing = []
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        if any(l.startswith("f ") for l in lines[i + 1:end]):
            bearing.append(i)
    if not heads or not bearing:
        first = next((m for m in material_names if m), None)
        head = f"mtllib {mtl_filename}\n" + (f"usemtl {safe_name(first, 'material')}\n" if first else "")
        return head + obj_text
    out, slot = [f"mtllib {mtl_filename}"], 0
    for i, l in enumerate(lines):
        out.append(l)
        if i in bearing:
            m = material_names[slot] if slot < len(material_names) else None
            out.append(f"usemtl {safe_name(m, 'material')}" if m else NO_SLOT)
            slot += 1
    return "\n".join(out)


def _walk_refs(value, path=""):
    """Yield (field path, reference dict) for every resolved PPtr in script values."""
    if isinstance(value, dict):
        if "ref" in value and ("type" in value or "external" in value):
            yield path, value
            return
        for k, v in value.items():
            yield from _walk_refs(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _walk_refs(v, f"{path}[{i}]")


NO_SLOT = "# no material slot: Unity does not draw this sub-mesh"


def obj_material_check(obj_text):
    """(face-bearing groups, groups accounted for) — equal when every sub-mesh has
    its usemtl, or is marked as one the original renderer never drew."""
    groups = usemtl = 0
    in_group_faces = False
    for l in obj_text.split("\n"):
        if l.startswith("g "):
            in_group_faces = False
        elif l.startswith("f ") and not in_group_faces:
            in_group_faces = True
            groups += 1
        elif l.startswith("usemtl ") or l == NO_SLOT:
            usemtl += 1
    return groups, usemtl


def build_manifest(engine, expected, by_type, mechanics=None, notes=None, extra=None):
    """The shape gen-coverage-report.py consumes. `extracted` is derived from
    by_type so the manifest can never over-claim what is on disk."""
    extracted = sum(int(v) for v in by_type.values())
    m = {"engine": engine,
         "assets": {"expected": int(expected), "extracted": extracted,
                    "by_type": dict(sorted(by_type.items()))},
         "mechanics": mechanics or [],
         "notes": notes or []}
    if extra:
        m.update(extra)
    return m


class NameAllocator:
    """Collision-free output paths; two assets may legitimately share a name.

    Compared case-insensitively: on macOS/Windows `Sphere_1.obj` and `sphere_1.obj`
    are the same file, and the second silently overwrote the first (one test
    extraction: 391 meshes written, 390 on disk)."""

    def __init__(self):
        self.seen = set()

    def path(self, directory, name, ext="", fallback="unnamed"):
        base = safe_name(name, fallback)
        candidate = os.path.join(directory, base + ext)
        i = 1
        while candidate.lower() in self.seen:
            candidate = os.path.join(directory, f"{base}_{i}{ext}")
            i += 1
        self.seen.add(candidate.lower())
        return candidate


# ---------------------------------------------------------------------------
# Mecanim clip decoding (StreamedClip / DenseClip / ConstantClip)
# ---------------------------------------------------------------------------

def decode_streamed_clip(data):
    """Decode a StreamedClip uint32 blob into [{time, curves:{index: coeffs}}].

    Layout per frame: time(f32), curveCount(u32), then curveCount records of
    index(u32) + 4 coefficients(f32). Same format AssetStudio/AssetRipper read.
    """
    if not data:
        return []
    buf = struct.pack(f"<{len(data)}I", *[int(x) & 0xFFFFFFFF for x in data])
    frames, off, n = [], 0, len(buf)
    while off + 8 <= n:
        time_v, curve_count = struct.unpack_from("<fI", buf, off)
        off += 8
        if curve_count > 100000 or off + curve_count * 20 > n:
            break
        curves = {}
        for _ in range(curve_count):
            idx, = struct.unpack_from("<I", buf, off)
            coeffs = struct.unpack_from("<4f", buf, off + 4)
            off += 20
            curves[idx] = list(coeffs)
        frames.append({"time": time_v, "curves": curves})
    return frames


def decode_dense_clip(dense):
    """DenseClip -> {frame_count, curve_count, sample_rate, begin_time, samples}."""
    samples = list(getattr(dense, "m_SampleArray", None) or [])
    return {"frame_count": int(getattr(dense, "m_FrameCount", 0) or 0),
            "curve_count": int(getattr(dense, "m_CurveCount", 0) or 0),
            "sample_rate": float(getattr(dense, "m_SampleRate", 0) or 0),
            "begin_time": float(getattr(dense, "m_BeginTime", 0) or 0),
            "samples": [float(s) for s in samples]}


# ---------------------------------------------------------------------------
# Package unpacking + split merge
# ---------------------------------------------------------------------------

def unpack_package(pkg_path, work_dir):
    """Unzip an APK/XAPK (and any nested APKs) -> list of extracted roots."""
    roots = []
    os.makedirs(work_dir, exist_ok=True)
    if os.path.isdir(pkg_path):
        # a folder of split APKs (base + asset pack + ABI config) is unpacked like an XAPK
        for name in sorted(os.listdir(pkg_path)):
            if not name.lower().endswith(".apk"):
                continue
            dest = os.path.join(work_dir, "unpacked", safe_name(name[:-4]))
            os.makedirs(dest, exist_ok=True)
            try:
                with zipfile.ZipFile(os.path.join(pkg_path, name)) as iz:
                    iz.extractall(dest)
                roots.append(dest)
            except zipfile.BadZipFile:
                continue
        return roots + [pkg_path]
    with zipfile.ZipFile(pkg_path) as z:
        inner = [n for n in z.namelist() if n.lower().endswith(".apk")]
        if inner:
            split_dir = os.path.join(work_dir, "split")
            os.makedirs(split_dir, exist_ok=True)
            z.extractall(split_dir)
            for name in inner:
                apk = os.path.join(split_dir, name)
                dest = os.path.join(work_dir, "unpacked",
                                    safe_name(os.path.basename(name)[:-4]))
                os.makedirs(dest, exist_ok=True)
                try:
                    with zipfile.ZipFile(apk) as iz:
                        iz.extractall(dest)
                    roots.append(dest)
                except zipfile.BadZipFile:
                    continue
        else:
            dest = os.path.join(work_dir, "unpacked", "base")
            os.makedirs(dest, exist_ok=True)
            z.extractall(dest)
            roots.append(dest)
    return roots


def find_data_dirs(roots):
    """Every assets/bin/Data directory across the unpacked roots."""
    out = []
    for r in roots:
        for dirpath, dirnames, _ in os.walk(r):
            if os.path.basename(dirpath) == "Data" and \
               os.path.basename(os.path.dirname(dirpath)) == "bin":
                out.append(dirpath)
                dirnames[:] = []
    return out


def find_bundle_files(roots, extra_dirs=()):
    """Addressables bundles: `assets/aa/**/*.bundle` in every unpacked root (an asset
    pack such as UnityDataAssetPack.apk carries the backdrop art there), plus any
    folder of bundles the caller pulled from a CDN or the device cache."""
    found = []
    for r in roots:
        for dirpath, _, files in os.walk(r):
            parts = dirpath.replace("\\", "/").split("/")
            if "aa" in parts and "assets" in parts:
                found += [os.path.join(dirpath, f) for f in files if f.endswith(".bundle")]
    for d in extra_dirs or ():
        for dirpath, _, files in os.walk(d):
            found += [os.path.join(dirpath, f) for f in files
                      if not f.startswith(".") and not f.endswith((".json", ".txt", ".md"))]
    return sorted(set(found))


def link_bundles(bundles, dst):
    """Hard-link bundles into the merged dir under unique flat names."""
    os.makedirs(dst, exist_ok=True)
    n = 0
    for i, b in enumerate(bundles):
        out = os.path.join(dst, f"bundle{i:04d}__{safe_name(os.path.basename(b))}")
        if not os.path.exists(out):
            try:
                os.link(b, out)
            except OSError:
                shutil.copy2(b, out)
        n += 1
    return n


def merge_sources(src_dirs, dst):
    """Flatten every Data dir into one directory, concatenating split chunks.

    UnityPy must see all files in a single environment or cross-file PPtrs
    (Sprite->Texture2D, Renderer->Material->Texture) never resolve.
    """
    os.makedirs(dst, exist_ok=True)
    linked = merged = 0
    for src in src_dirs:
        names = [f for f in os.listdir(src) if os.path.isfile(os.path.join(src, f))]
        groups = split_groups(names)
        grouped = {n for parts in groups.values() for n in parts}
        for f in names:
            if f in grouped:
                continue
            out = os.path.join(dst, f)
            linked += 1          # counts files in the merged set, so a reused scratch reports the same
            if os.path.exists(out):
                continue
            try:
                os.link(os.path.join(src, f), out)
            except OSError:
                shutil.copy2(os.path.join(src, f), out)
        for base, parts in groups.items():
            out = os.path.join(dst, base)
            merged += 1
            if os.path.exists(out):
                continue
            with open(out, "wb") as o:
                for p in parts:
                    with open(os.path.join(src, p), "rb") as i:
                        shutil.copyfileobj(i, o)
    return {"linked": linked, "merged_split_groups": merged}


# ---------------------------------------------------------------------------
# UnityPy helpers
# ---------------------------------------------------------------------------

def find_il2cpp(roots):
    """(libil2cpp.so, global-metadata.dat) from the unpacked roots, or (None, None).
    64-bit first: it is the build the store serves to most devices."""
    libs, meta = [], None
    for r in roots:
        for dirpath, _, files in os.walk(r):
            if "libil2cpp.so" in files:
                libs.append(os.path.join(dirpath, "libil2cpp.so"))
            if "global-metadata.dat" in files and meta is None:
                meta = os.path.join(dirpath, "global-metadata.dat")
    libs.sort(key=lambda p: (0 if "arm64" in p else 1 if "armeabi" in p else 2, p))
    return (libs[0] if libs else None), meta


def make_script_types(unity_version, lib_path, meta_path):
    """UnityPy's TypeTreeGenerator, rebuilding the type trees an IL2CPP release
    strips from MonoBehaviours out of libil2cpp.so + global-metadata.dat.

    This is what makes script field values readable: which sprite an Image draws,
    which prefab a launcher controller fires, a CanvasScaler's reference resolution.
    UnityPy's wrapper asks for "<Assembly>.dll" but the generator indexes
    assemblies without the extension, so every lookup failed; we ask both ways.
    A class it cannot build returns None, which UnityPy turns into a header-only
    read instead of losing the component."""
    from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
    from UnityPy.helpers.TypeTreeNode import TypeTreeNode

    class ScriptTypes(TypeTreeGenerator):
        def get_nodes_up(self, assembly, fullname):
            key = (assembly, fullname)
            if key in self.cache:
                return self.cache[key]
            base = None
            for asm in (assembly[:-4] if assembly.endswith(".dll") else assembly, assembly):
                try:
                    base = self.get_nodes(asm, fullname)
                    if base:
                        break
                except Exception:
                    base = None
            node = None
            if base:
                node = TypeTreeNode.from_list([
                    TypeTreeNode(b.m_Level, b.m_Type, b.m_Name, 0, 0, m_MetaFlag=b.m_MetaFlag)
                    for b in base])
            self.cache[key] = node
            return node

    g = ScriptTypes(unity_version)
    with open(lib_path, "rb") as a, open(meta_path, "rb") as b:
        g.load_il2cpp(a.read(), b.read())
    return g


def oid(o):
    """Stable identity of a Unity object: `<serialized file>:<path id>`. Names are
    not unique (a 30 kg showcase "Ball" shadowed the 1.2 kg ball the game fires)."""
    r = getattr(o, "object_reader", None) or o      # a parsed object or its reader
    try:
        return f"{os.path.basename(r.assets_file.name or '?')}:{r.path_id}"
    except Exception:
        return None


def _read(obj):
    try:
        if getattr(getattr(obj, "type", None), "name", None) == "MonoBehaviour":
            try:
                return obj.read(check_read=False)
            except Exception:
                return obj.parse_monobehaviour_head()   # class name still known
        return obj.read()
    except Exception:
        return None


def _reader_of(pptr):
    """The ObjectReader a PPtr points at, or None."""
    if pptr is None or not getattr(pptr, "m_PathID", 0):
        return None
    try:
        return pptr.deref()
    except Exception:
        return None


def _deref(pptr):
    if pptr is None:
        return None
    r = _reader_of(pptr)
    if r is not None:
        return _read(r)
    try:
        return pptr.read()
    except Exception:
        return None


def _items(container):
    if container is None:
        return []
    if hasattr(container, "items"):
        return list(container.items())
    return list(container)


def _vec(v, keys=("x", "y", "z", "w")):
    if v is None:
        return None
    out = [getattr(v, k, None) for k in keys]
    out = [float(x) for x in out if x is not None]
    return out or None


def _ctype(c):
    """Engine type of a parsed component. A MonoBehaviour decoded with a generated
    type tree comes back as an `UnknownObject`, so the class name lies."""
    r = getattr(c, "object_reader", None)
    try:
        return r.type.name if r is not None else type(c).__name__
    except Exception:
        return type(c).__name__


def _components(go):
    out = []
    for c in getattr(go, "m_Component", None) or []:
        target = c if hasattr(c, "read") else getattr(c, "component", None)
        o = _deref(target)
        if o is not None:
            out.append(o)
    return out


def _transform_of(go):
    for c in _components(go):
        if _ctype(c) in ("Transform", "RectTransform"):
            return c
    return None


def _children(go):
    tr = _transform_of(go)
    if tr is None:
        return []
    out = []
    for ch in getattr(tr, "m_Children", None) or []:
        t = _deref(ch)
        if t is None:
            continue
        g = _deref(getattr(t, "m_GameObject", None))
        if g is not None:
            out.append(g)
    return out


def _script_name(mb):
    s = _deref(getattr(mb, "m_Script", None))
    return getattr(s, "m_ClassName", None) if s else None


_TMP = ["m_text", "m_fontAsset", "m_sharedMaterial", "m_fontSize", "m_fontSizeBase",
        "m_enableAutoSizing", "m_fontSizeMin", "m_fontSizeMax", "m_fontColor", "m_fontColor32",
        "m_characterSpacing", "m_wordSpacing", "m_lineSpacing", "m_HorizontalAlignment",
        "m_VerticalAlignment", "m_textAlignment", "m_fontStyle", "m_enableWordWrapping",
        "m_TextWrappingMode", "m_overflowMode", "m_margin", "m_RaycastTarget"]
_LAYOUT = ["m_Padding", "m_Spacing", "m_ChildAlignment", "m_CellSize", "m_StartCorner",
           "m_StartAxis", "m_Constraint", "m_ConstraintCount", "m_ChildControlWidth",
           "m_ChildControlHeight", "m_ChildForceExpandWidth", "m_ChildForceExpandHeight",
           "m_ReverseArrangement"]
# What each uGUI component draws, by its serialized field names. The full values
# of every script are in scripts/; this is the part a screen rebuild needs inline.
UI_SUMMARY = {
    "Image": ["m_Sprite", "m_Type", "m_Color", "m_Material", "m_PreserveAspect", "m_FillCenter",
              "m_FillMethod", "m_FillAmount", "m_FillOrigin", "m_FillClockwise",
              "m_PixelsPerUnitMultiplier", "m_UseSpriteMesh", "m_RaycastTarget"],
    "RawImage": ["m_Texture", "m_Color", "m_UVRect", "m_Material", "m_RaycastTarget"],
    "TextMeshProUGUI": _TMP, "TextMeshPro": _TMP,
    "Text": ["m_Text", "m_FontData", "m_Color", "m_Material"],
    "Button": ["m_Transition", "m_TargetGraphic", "m_Colors", "m_SpriteState", "m_Interactable"],
    "Toggle": ["m_Transition", "m_TargetGraphic", "graphic", "m_IsOn", "m_Group", "m_Interactable"],
    "Slider": ["m_FillRect", "m_HandleRect", "m_Direction", "m_MinValue", "m_MaxValue", "m_Value"],
    "ScrollRect": ["m_Content", "m_Viewport", "m_Horizontal", "m_Vertical", "m_MovementType"],
    "CanvasScaler": ["m_UiScaleMode", "m_ReferencePixelsPerUnit", "m_ScaleFactor",
                     "m_ReferenceResolution", "m_ScreenMatchMode", "m_MatchWidthOrHeight",
                     "m_PhysicalUnit", "m_FallbackScreenDPI", "m_DefaultSpriteDPI"],
    "HorizontalLayoutGroup": _LAYOUT, "VerticalLayoutGroup": _LAYOUT, "GridLayoutGroup": _LAYOUT,
    "LayoutElement": ["m_IgnoreLayout", "m_MinWidth", "m_MinHeight", "m_PreferredWidth",
                      "m_PreferredHeight", "m_FlexibleWidth", "m_FlexibleHeight"],
    "ContentSizeFitter": ["m_HorizontalFit", "m_VerticalFit"],
    "AspectRatioFitter": ["m_AspectMode", "m_AspectRatio"],
    "Mask": ["m_ShowMaskGraphic"], "RectMask2D": ["m_Padding", "m_Softness"],
    "Outline": ["m_EffectColor", "m_EffectDistance", "m_UseGraphicAlpha"],
    "Shadow": ["m_EffectColor", "m_EffectDistance", "m_UseGraphicAlpha"],
}


def _is_graphic(fields):
    """uGUI Graphic subclass by its serialized base fields."""
    return bool(fields) and all(k in fields for k in ("m_Material", "m_Color", "m_RaycastTarget"))


def _pick(fields, names):
    if names is None or fields is None:
        return None
    return {k: fields[k] for k in names if k in fields}


def _father_matches(child_go, parent_tr):
    """A child reached through the parent's m_Children must point back with m_Father."""
    tr = _transform_of(child_go)
    if tr is None or parent_tr is None:
        return True
    back = _reader_of(getattr(tr, "m_Father", None))
    return back is not None and oid(back) == oid(parent_tr)


def _has_canvas_ancestor(go):
    tr = _transform_of(go)
    for _ in range(256):
        tr = _father(tr)
        if tr is None:
            return False
        g = _deref(getattr(tr, "m_GameObject", None))
        if g is not None and any(_ctype(c) == "Canvas" for c in _components(g)):
            return True
    return False


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def _qrot(q, v):
    x, y, z, w = q
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def _world_trs(tr, limit=256):
    """World position, rotation (x,y,z,w) and lossy scale of a Transform, composed
    up the m_Father chain — what a camera or light needs to be placed."""
    chain = []
    while tr is not None and len(chain) < limit:
        chain.append(tr)
        tr = _father(tr)
    pos, rot, scl = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)
    for t in reversed(chain):
        lp = _vec(getattr(t, "m_LocalPosition", None), ("x", "y", "z")) or [0, 0, 0]
        lr = _vec(getattr(t, "m_LocalRotation", None)) or [0, 0, 0, 1]
        ls = _vec(getattr(t, "m_LocalScale", None), ("x", "y", "z")) or [1, 1, 1]
        off = _qrot(rot, (lp[0] * scl[0], lp[1] * scl[1], lp[2] * scl[2]))
        pos = (pos[0] + off[0], pos[1] + off[1], pos[2] + off[2])
        rot = _qmul(rot, tuple(lr))
        scl = (scl[0] * ls[0], scl[1] * ls[1], scl[2] * ls[2])
    return {"position": list(pos), "rotation": list(rot), "lossy_scale": list(scl)}


def _placed(component):
    """{gameObject, path, world TRS} of the GameObject a component sits on."""
    go = _deref(getattr(component, "m_GameObject", None))
    if go is None:
        return {}
    return dict({"gameObject": go.m_Name, "path": _go_path(go)}, **_world_trs(_transform_of(go)))


def _father(tr):
    """Parent Transform through m_Father — the engine's own back-link."""
    return _deref(getattr(tr, "m_Father", None)) if tr is not None else None


def _go_path(go, limit=64):
    """`Root/Child/Leaf` from the m_Father chain; unambiguous where names repeat."""
    parts, tr = [], _transform_of(go) if go is not None else None
    if go is not None:
        parts.append(getattr(go, "m_Name", "") or "?")
    while tr is not None and len(parts) < limit:
        tr = _father(tr)
        if tr is None:
            break
        g = _deref(getattr(tr, "m_GameObject", None))
        parts.append(getattr(g, "m_Name", "") or "?")
    return "/".join(reversed(parts))


def _mesh_ref(component, externals_of):
    """Resolve a MeshFilter/SkinnedMeshRenderer/MeshCollider mesh reference.

    Returns (mesh_name, kind). `kind` is None for a resolved mesh, or a
    'builtin:'/'external:'/'unresolved' marker when it cannot be read.

    Always dereference first: a non-zero m_FileID usually just means another
    serialized file in the same package, which UnityPy resolves fine. Only when
    the deref genuinely fails is the reference outside the package — and a
    'Library/unity default resources' target is a built-in primitive, a finding
    rather than a failure.
    """
    pptr = getattr(component, "m_Mesh", None)
    if pptr is None:
        return None, None
    if not getattr(pptr, "m_PathID", 1):
        return None, None          # null reference, nothing was assigned
    m = _deref(pptr)
    name = getattr(m, "m_Name", None) if m is not None else None
    if name:
        return name, None
    file_id = getattr(pptr, "m_FileID", 0) or 0
    if file_id:
        return None, external_kind(file_id, externals_of(component))
    return None, "unresolved"


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

# Path ids of the meshes in "Library/unity default resources" (stable across versions)
BUILTIN_MESHES = {10202: "Cube", 10206: "Cylinder", 10207: "Sphere", 10208: "Capsule",
                  10209: "Plane", 10210: "Quad"}

HEADER_FIELDS = ("m_GameObject", "m_Enabled", "m_Script", "m_Name", "m_EditorHideFlags",
                 "m_EditorClassIdentifier")


class Extractor:
    def __init__(self, merged_dir, out_dir, verbose=True, il2cpp=(None, None)):
        import UnityPy  # lazy: keeps the pure helpers stdlib-importable
        self.UnityPy = UnityPy
        self.merged = merged_dir
        self.out = out_dir
        self.verbose = verbose
        self.env = UnityPy.load(merged_dir)
        self.alloc = NameAllocator()
        self.counts = collections.Counter()
        self.errors = collections.Counter()
        self.notes = []
        self.mesh_files = {}      # mesh id -> path
        self.mesh_by_name = collections.defaultdict(list)    # name -> [mesh ids]
        self.texture_files = {}   # texture id -> path
        self.texture_by_name = collections.defaultdict(list)
        self.sprite_files = {}    # sprite id -> path
        self.mesh_index = {}      # mesh id -> {name, file, submeshes}
        self.skins = {}           # mesh id -> (bindposes, bone indices, bone weights)
        self.materials = {}       # material id -> payload (materials.json)
        self.objects = list(self.env.objects)
        self.total_objects = len(self.objects)
        self.type_counts = collections.Counter(o.type.name for o in self.objects)
        self.script_types = None
        self._script_cache, self._name_cache, self._mb_cache = {}, {}, {}
        lib, meta = il2cpp
        if lib and meta and self.objects:
            versions = collections.Counter(
                getattr(o.assets_file, "unity_version", None) for o in self.objects[:2000])
            version = next((v for v, _ in versions.most_common() if v), None)
            try:
                self.script_types = make_script_types(version, lib, meta)
                self.env.typetree_generator = self.script_types
            except Exception as e:  # noqa: BLE001 — a missing native lib must not stop extraction
                self.notes.append(f"Script type trees could not be rebuilt from {os.path.basename(lib)} "
                                  f"({type(e).__name__}: {e}); MonoBehaviour values are header-only.")
        elif self.type_counts.get("MonoBehaviour"):
            self.notes.append("No libil2cpp.so + global-metadata.dat found; MonoBehaviour field "
                              "values could not be decoded (a Mono build needs Managed/*.dll).")

    # -- script values -----------------------------------------------------
    def script_of(self, mb):
        """(assembly, namespace, class) of a MonoBehaviour object or reader."""
        r = getattr(mb, "object_reader", None) or mb
        key = oid(r)
        if key in self._script_cache:
            return self._script_cache[key]
        info = (None, None, None)
        try:
            head = r.parse_monobehaviour_head()
            s = _deref(head.m_Script)
            if s is not None:
                info = (getattr(s, "m_AssemblyName", None), getattr(s, "m_Namespace", None),
                        getattr(s, "m_ClassName", None))
        except Exception:
            pass
        self._script_cache[key] = info
        return info

    def name_of(self, r):
        """Readable name of the object a reference points at; components take
        their GameObject's name."""
        key = oid(r)
        if key in self._name_cache:
            return self._name_cache[key]
        name = None
        try:
            try:
                name = r.peek_name()
            except Exception:
                name = None
            if not name and r.type.name != "GameObject":
                o = _read(r)
                go = _reader_of(getattr(o, "m_GameObject", None)) if o is not None else None
                name = go.peek_name() if go is not None else getattr(o, "m_Name", None)
        except Exception:
            name = None
        self._name_cache[key] = name
        return name

    def ref(self, src, file_id, path_id):
        """A raw PPtr from a dict-mode read -> {"ref": id, "type", "name"}."""
        if not path_id:
            return None
        from UnityPy.classes.PPtr import PPtr
        try:
            r = PPtr(m_FileID=int(file_id), m_PathID=int(path_id), assetsfile=src.assets_file).deref()
        except Exception:
            ext = None
            try:
                ext = src.assets_file.externals[int(file_id) - 1].path if file_id else None
            except Exception:
                pass
            return {"ref": None, "external": ext, "path_id": int(path_id)}
        return {"ref": oid(r), "type": r.type.name, "name": self.name_of(r)}

    def plain(self, src, v, depth=0):
        """Dict-mode typetree values -> JSON, with every PPtr resolved."""
        if depth > 48:
            self.errors["script-values:too-deep"] += 1
            return "<too deep>"
        if isinstance(v, dict):
            if len(v) == 2 and "m_FileID" in v and "m_PathID" in v:
                return self.ref(src, v["m_FileID"], v["m_PathID"])
            return {str(k): self.plain(src, x, depth + 1) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            if len(v) > 50000:
                self.errors["script-values:huge-array"] += 1
                return {"length": len(v), "head": [self.plain(src, x, depth + 1) for x in v[:500]]}
            return [self.plain(src, x, depth + 1) for x in v]
        if isinstance(v, (bytes, bytearray, memoryview)):
            return f"<{len(v)} bytes>"
        if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
            return str(v)
        return v

    def mb_values(self, mb):
        """(class, fields, complete?) for a MonoBehaviour — the values a stripped
        IL2CPP build hides, rebuilt from the generated type tree. Cached."""
        r = getattr(mb, "object_reader", None) or mb
        key = oid(r)
        if key in self._mb_cache:
            return self._mb_cache[key]
        asm, ns, cn = self.script_of(r)
        fields, complete = {}, False
        full = f"{ns}.{cn}" if ns else cn
        if self.script_types is not None and asm and cn:
            complete = self.script_types.get_nodes_up(asm, full) is not None
        try:
            raw = r.read_typetree(wrap=False, check_read=False)
            fields = {k: self.plain(r, v) for k, v in raw.items() if k not in HEADER_FIELDS}
        except Exception:
            complete = False
            self.errors["MonoBehaviour:values"] += 1
        out = ({"assembly": asm, "namespace": ns, "class": cn}, fields, complete)
        self._mb_cache[key] = out
        return out

    def export_scripts(self):
        """Every MonoBehaviour's field values, one JSONL per class, plus a flat
        table of every object reference a script holds. `grep BallPrefab
        scripts/references.tsv` answers "which prefab does the game fire" — the
        question a name search answered wrongly."""
        d = self.dir("scripts")
        by_class = collections.defaultdict(list)
        refs = []
        read = complete = 0
        for o in self.objects:
            if o.type.name != "MonoBehaviour":
                continue
            script, fields, ok = self.mb_values(o)
            read += 1
            complete += bool(ok)
            head = _read(o)
            go = _reader_of(getattr(head, "m_GameObject", None)) if head is not None else None
            row = {"id": oid(o),
                   "gameObject": {"ref": oid(go), "name": self.name_of(go)} if go is not None else None,
                   "enabled": bool(getattr(head, "m_Enabled", True)) if head is not None else None,
                   "values_complete": ok, "fields": fields}
            cls = ".".join(p for p in (script["namespace"], script["class"]) if p) or "?"
            by_class[(script["assembly"] or "?", cls)].append(row)
            for path, r in _walk_refs(fields):
                refs.append((oid(o), cls, row["gameObject"]["name"] if row["gameObject"] else "",
                             path, r.get("ref") or "", r.get("type") or "", r.get("name") or ""))
        index = []
        for (asm, cls), rows in sorted(by_class.items()):
            sub = self.dir("scripts", safe_name(asm))
            path = os.path.join(sub, safe_name(cls) + ".jsonl")
            with open(path, "w") as f:
                for row in rows:
                    f.write(json.dumps(_finite(row), ensure_ascii=False, default=str, allow_nan=False) + "\n")
            index.append({"assembly": asm, "class": cls, "count": len(rows),
                          "values_complete": sum(1 for r in rows if r["values_complete"]),
                          "file": os.path.relpath(path, self.out)})
        self.write_json("scripts/index.json", index)
        with open(os.path.join(d, "references.tsv"), "w") as f:
            f.write("from_id\tfrom_class\tgameobject\tfield\tto_id\tto_type\tto_name\n")
            for row in refs:
                f.write("\t".join(str(c).replace("\t", " ").replace("\n", " ") for c in row) + "\n")
        self.write_fields_table(by_class)
        self.counts["monobehaviours"] = read
        self.mb_stats = {"total": read, "values_complete": complete, "classes": len(by_class)}
        if read and complete < read:
            self.notes.append(f"{read - complete}/{read} MonoBehaviours have header-only values "
                              "(no generated type tree for their class) — scripts/index.json lists which.")
        return self.mb_stats

    def write_fields_table(self, by_class):
        """scripts/script-fields.tsv: class -> serialized field, type (declaration order)."""
        if self.script_types is None:
            return
        with open(os.path.join(self.out, "scripts", "script-fields.tsv"), "w") as f:
            f.write("assembly\tclass\tfield\ttype\n")
            for asm, cls in sorted(by_class):
                node = self.script_types.get_nodes_up(asm, cls)
                for ch in (getattr(node, "m_Children", None) or []):
                    if ch.m_Name in HEADER_FIELDS:
                        continue
                    f.write(f"{asm}\t{cls}\t{ch.m_Name}\t{ch.m_Type}\n")

    # -- infrastructure ---------------------------------------------------
    def log(self, msg):
        if self.verbose:
            print(msg, flush=True)

    def dir(self, *parts):
        d = os.path.join(self.out, *parts)
        os.makedirs(d, exist_ok=True)
        return d

    def write_json(self, rel, payload):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)
        return path

    def externals_of(self, obj):
        try:
            return [e.path for e in obj.assets_file.externals]
        except Exception:
            return []

    # -- flat asset export -------------------------------------------------
    def export_textures(self):
        d = self.dir("textures")
        formats = {}
        for o in self.objects:
            if o.type.name != "Texture2D":
                continue
            t = _read(o)
            if t is None:
                self.errors["Texture2D:read"] += 1
                continue
            try:
                img = t.image
            except Exception:
                self.errors["Texture2D:decode"] += 1
                continue
            if img is None:
                self.errors["Texture2D:empty"] += 1
                continue
            name = t.m_Name or f"unnamed_{o.path_id}"
            path = self.alloc.path(d, name, ".png", f"unnamed_{o.path_id}")
            try:
                img.save(path)
            except Exception:
                self.errors["Texture2D:save"] += 1
                continue
            fmt_name, lossless = texture_format_info(getattr(t, "m_TextureFormat", None))
            formats[os.path.basename(path)] = {
                "id": oid(o),
                "name": t.m_Name, "width": t.m_Width, "height": t.m_Height,
                "format": fmt_name, "lossless": lossless,
                "mipmaps": bool(getattr(t, "m_MipCount", 0) or 0 > 1),
            }
            self.texture_files[oid(o)] = path
            self.texture_by_name[t.m_Name].append(oid(o))
            self.counts["textures"] += 1
        self.write_json("textures/texture-formats.json", formats)
        lossy = sum(1 for v in formats.values() if not v["lossless"])
        if lossy:
            self.notes.append(
                f"{lossy}/{len(formats)} textures were compressed (ASTC/ETC/DXT) in the "
                "package and are exported as decoded PNG — re-compressing them costs a "
                "second generation of quality loss. See textures/texture-formats.json.")
        return formats

    def export_sprites(self):
        d = self.dir("sprites")
        meta, bordered = {}, 0
        for o in self.objects:
            if o.type.name != "Sprite":
                continue
            s = _read(o)
            if s is None:
                self.errors["Sprite:read"] += 1
                continue
            try:
                img = s.image
            except Exception:
                self.errors["Sprite:decode"] += 1
                continue
            if img is None:
                continue
            path = self.alloc.path(d, s.m_Name, ".png", f"sprite_{o.path_id}")
            img.save(path)
            self.sprite_files[oid(o)] = path
            border = _vec(getattr(s, "m_Border", None)) or [0, 0, 0, 0]
            if any(border):
                bordered += 1
            tex = _reader_of(getattr(getattr(s, "m_RD", None), "texture", None))
            alpha_box = None
            try:
                alpha_box = img.getchannel("A").getbbox() if "A" in img.getbands() else None
            except Exception:
                pass
            meta[os.path.basename(path)] = {
                "id": oid(o),
                "texture": oid(tex) if tex is not None else None,
                "size": [img.width, img.height],
                # painted extent inside the sprite rect: a reference screenshot
                # measures THIS, not the rect a RectTransform stretches
                "alpha_bbox": list(alpha_box) if alpha_box else None,
                "name": s.m_Name,
                "pixels_per_unit": float(getattr(s, "m_PixelsToUnits", 0) or 0),
                "pivot": _vec(getattr(s, "m_Pivot", None), ("x", "y")),
                "border_LBRT": border,
                "rect": _vec(getattr(s, "m_Rect", None), ("x", "y", "width", "height")),
            }
            self.counts["sprites"] += 1
        self.write_json("sprites/sprite-meta.json", meta)
        if bordered:
            self.notes.append(
                f"{bordered} sprites carry a non-zero 9-slice border — importing them "
                "without sprites/sprite-meta.json visibly stretches every UI frame.")
        return meta

    def export_meshes(self):
        d = self.dir("meshes")
        for o in self.objects:
            if o.type.name != "Mesh":
                continue
            m = _read(o)
            if m is None:
                self.errors["Mesh:read"] += 1
                continue
            try:
                body = m.export()
            except Exception:
                self.errors["Mesh:export"] += 1
                continue
            path = self.alloc.path(d, m.m_Name, ".obj", f"mesh_{o.path_id}")
            with open(path, "w") as f:
                f.write(body)
            self.mesh_files[oid(o)] = path
            self.mesh_by_name[m.m_Name].append(oid(o))
            skin = _skin_of(m)
            if skin is not None:
                self.skins[oid(o)] = skin
            self.mesh_index[oid(o)] = {"name": m.m_Name, "file": os.path.basename(path),
                                       "submeshes": len(getattr(m, "m_SubMeshes", None) or [])}
            self.counts["meshes"] += 1
        self.write_json("meshes/meshes.json", self.mesh_index)

    def export_audio(self):
        d = self.dir("audio")
        for o in self.objects:
            if o.type.name != "AudioClip":
                continue
            a = _read(o)
            if a is None:
                self.errors["AudioClip:read"] += 1
                continue
            try:
                samples = a.samples or {}
            except Exception:
                self.errors["AudioClip:decode"] += 1
                continue
            if not samples:
                self.errors["AudioClip:empty"] += 1
                continue
            for nm, data in samples.items():
                path = self.alloc.path(d, nm, "" if "." in nm else ".wav")
                with open(path, "wb") as f:
                    f.write(data)
                self.counts["audio"] += 1

    def export_fonts(self):
        """Real TTF/OTF bytes — m_FontData may arrive as a list of ints."""
        d = self.dir("fonts")
        info = {}
        for o in self.objects:
            if o.type.name != "Font":
                continue
            fo = _read(o)
            if fo is None:
                self.errors["Font:read"] += 1
                continue
            raw = getattr(fo, "m_FontData", None)
            atlas = _deref(getattr(fo, "m_Texture", None))
            entry = {
                "family_names": list(getattr(fo, "m_FontNames", None) or []),
                "font_size": float(getattr(fo, "m_FontSize", 0) or 0),
                "ascent": float(getattr(fo, "m_Ascent", 0) or 0),
                "line_spacing": float(getattr(fo, "m_LineSpacing", 0) or 0),
                "kerning_pairs": len(getattr(fo, "m_KerningValues", None) or []),
                "character_rects": len(getattr(fo, "m_CharacterRects", None) or []),
                "atlas_texture": getattr(atlas, "m_Name", None) if atlas else None,
                "file": None,
            }
            if raw:
                data = bytes(raw) if not isinstance(raw, (bytes, bytearray)) else bytes(raw)
                path = self.alloc.path(d, fo.m_Name, font_extension(data), f"font_{o.path_id}")
                with open(path, "wb") as f:
                    f.write(data)
                entry["file"] = os.path.basename(path)
                self.counts["fonts"] += 1
            else:
                self.errors["Font:no-data"] += 1
            info[fo.m_Name or f"font_{o.path_id}"] = entry
        self.write_json("fonts/fonts.json", info)
        self.notes.append(
            "TextMeshPro FontAssets are ScriptableObjects, so their glyph tables are "
            "stripped — import the extracted TTF/OTF and regenerate the SDF asset in Unity.")
        return info

    def export_textassets(self):
        """Route level JSON, Spine skeletons and plain text to their own pools."""
        levels_dir = self.dir("levels")
        spine_dir = self.dir("spine")
        text_dir = self.dir("text")
        levels = collections.defaultdict(list)
        for o in self.objects:
            if o.type.name != "TextAsset":
                continue
            t = _read(o)
            if t is None:
                self.errors["TextAsset:read"] += 1
                continue
            script = t.m_Script
            raw = (script.encode("utf-8", "surrogateescape")
                   if isinstance(script, str) else bytes(script or b""))
            name = t.m_Name or f"text_{o.path_id}"
            stem = name[:-5] if name.lower().endswith(".json") else name
            level_no = level_index(stem)
            if level_no is not None:
                path = self.alloc.path(levels_dir, name if name.endswith(".json")
                                       else name + ".json")
                self.counts["levels"] += 1
                try:
                    levels[level_no].append(json.loads(raw.decode("utf-8", "replace")))
                except Exception:
                    self.errors["level:parse"] += 1
            elif name.endswith((".skel", ".atlas")) or "skel" in name.lower():
                path = self.alloc.path(spine_dir, name)
                self.counts["spine"] += 1
            else:
                path = self.alloc.path(text_dir, name,
                                       "" if "." in name else ".txt")
                self.counts["text"] += 1
            with open(path, "wb") as f:
                f.write(raw)
        return levels

    # -- deep capture ------------------------------------------------------
    def export_materials(self):
        mats = {}
        for o in self.objects:
            if o.type.name != "Material":
                continue
            m = _read(o)
            if m is None:
                self.errors["Material:read"] += 1
                continue
            sp = getattr(m, "m_SavedProperties", None)
            textures = {}
            for k, v in _items(getattr(sp, "m_TexEnvs", None)):
                tr = _reader_of(getattr(v, "m_Texture", None))
                tex = _read(tr) if tr is not None else None
                if tex is not None and getattr(tex, "m_Name", None):
                    textures[k] = {"texture": tex.m_Name, "texture_id": oid(tr),
                                   "scale": _vec(getattr(v, "m_Scale", None), ("x", "y")),
                                   "offset": _vec(getattr(v, "m_Offset", None), ("x", "y"))}
            shader = _deref(getattr(m, "m_Shader", None))
            shader_name = None
            if shader is not None:
                pf = getattr(shader, "m_ParsedForm", None)
                shader_name = getattr(pf, "m_Name", None) or getattr(shader, "m_Name", None)
            # keyed by identity: in one test game 216 materials shared 200 names,
            # and a name key silently kept one of each pair
            mats[oid(o)] = {
                "name": m.m_Name or f"material_{o.path_id}",
                "shader": shader_name,
                "textures": textures,
                "floats": {k: round(float(v), 5) for k, v in _items(getattr(sp, "m_Floats", None))},
                "colors": {k: [round(float(getattr(c, ch, 0.0)), 4) for ch in ("r", "g", "b", "a")]
                           for k, c in _items(getattr(sp, "m_Colors", None))},
                "keywords": list(getattr(m, "m_ValidKeywords", None) or []),
                "render_queue": getattr(m, "m_CustomRenderQueue", None),
            }
            self.counts["materials"] += 1
        names = collections.Counter(v["name"] for v in mats.values())
        for v in mats.values():
            v["name_dup"] = names[v["name"]]
        self.materials = mats
        self.write_json("materials.json", mats)
        return mats

    def export_shaders(self):
        """Shader interface: name, full property table, tags, keywords."""
        d = self.dir("shaders")
        index = []
        for o in self.objects:
            if o.type.name != "Shader":
                continue
            sh = _read(o)
            if sh is None:
                self.errors["Shader:read"] += 1
                continue
            pf = getattr(sh, "m_ParsedForm", None)
            name = getattr(pf, "m_Name", None) or sh.m_Name or f"shader_{o.path_id}"
            props = []
            for p in (getattr(getattr(pf, "m_PropInfo", None), "m_Props", None) or []):
                props.append({
                    "name": getattr(p, "m_Name", None),
                    "label": getattr(p, "m_Description", None),
                    "type": getattr(p, "m_Type", None),
                    "flags": getattr(p, "m_Flags", None),
                    "attributes": list(getattr(p, "m_Attributes", None) or []),
                    "default": [getattr(p, f"m_DefValue_{i}_", None) for i in range(4)],
                    "default_texture": getattr(getattr(p, "m_DefTexture", None),
                                               "m_DefaultName", None),
                })
            subshaders = []
            for ss in (getattr(pf, "m_SubShaders", None) or []):
                tags = getattr(getattr(ss, "m_Tags", None), "tags", None)
                subshaders.append({
                    "lod": getattr(ss, "m_LOD", None),
                    "passes": len(getattr(ss, "m_Passes", None) or []),
                    "tags": dict(_items(tags)),
                })
            origin, note = shader_origin(name)
            payload = {"name": name, "origin": origin, "source_note": note,
                       "fallback": getattr(pf, "m_FallbackName", None),
                       "keywords": list(getattr(pf, "m_KeywordNames", None) or []),
                       "properties": props, "subshaders": subshaders,
                       "compiled_blob_bytes": len(getattr(sh, "compressedBlob", None) or b""),
                       "hlsl": "not recoverable — compiled per platform"}
            path = self.alloc.path(d, name.replace("/", "_"), ".json",
                                   f"shader_{o.path_id}")
            with open(path, "w") as f:
                _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)
            index.append({"name": name, "origin": origin, "note": note,
                          "properties": len(props), "file": os.path.basename(path)})
            self.counts["shaders"] += 1
        self._write_shader_readme(index)
        return index

    def _write_shader_readme(self, index):
        groups = collections.defaultdict(list)
        for s in index:
            groups[s["origin"]].append(s)
        lines = ["# Shaders", "",
                 "Shader **interfaces** are fully recoverable from the package; the HLSL",
                 "and compiled bytecode are not. Each JSON here carries the real shader",
                 "name, the complete property table (internal name, display label, type,",
                 "default value, default texture), subshader tags, LOD, pass count and",
                 "keyword list — enough to re-declare the shader exactly and re-author",
                 "only the body.", ""]
        titles = {"builtin": "Built-in / package shaders — drop-in, nothing to do",
                  "commercial": "Commercial shaders — buy the package, then apply materials.json values",
                  "custom": "Custom to this game — must be re-authored against the property table"}
        for origin in ("builtin", "commercial", "custom"):
            items = groups.get(origin)
            if not items:
                continue
            lines += [f"## {titles[origin]}", "", "| Shader | Properties | Source | File |",
                      "|---|---|---|---|"]
            for s in sorted(items, key=lambda x: x["name"]):
                lines.append(f"| `{s['name']}` | {s['properties']} | {s['note']} | `{s['file']}` |")
            lines.append("")
        with open(os.path.join(self.out, "shaders", "README.md"), "w") as f:
            f.write("\n".join(lines))

    def export_particles(self):
        """Every ParticleSystem module. This is a large share of a game's look."""
        d = self.dir("particles")
        by_go = {}
        module_fields = ("InitialModule", "EmissionModule", "ShapeModule", "VelocityModule",
                         "ForceModule", "ColorModule", "ColorBySpeedModule", "SizeModule",
                         "SizeBySpeedModule", "RotationModule", "RotationBySpeedModule",
                         "ClampVelocityModule", "CollisionModule", "SubModule", "UVModule",
                         "TrailModule", "NoiseModule", "LightsModule")
        for o in self.objects:
            if o.type.name != "ParticleSystem":
                continue
            ps = _read(o)
            if ps is None:
                self.errors["ParticleSystem:read"] += 1
                continue
            go = _deref(getattr(ps, "m_GameObject", None))
            go_name = getattr(go, "m_Name", None) or f"ps_{o.path_id}"
            payload = {"gameObject": go_name,
                       "lengthInSec": getattr(ps, "lengthInSec", None),
                       "looping": getattr(ps, "looping", None),
                       "prewarm": getattr(ps, "prewarm", None),
                       "playOnAwake": getattr(ps, "playOnAwake", None),
                       "moveWithTransform": getattr(ps, "moveWithTransform", None),
                       "modules": {}}
            for mod in module_fields:
                m = getattr(ps, mod, None)
                if m is None:
                    continue
                payload["modules"][mod] = self._dump_struct(m, depth=16, cap=100000)
            if go is not None:
                for c in _components(go):
                    if _ctype(c) == "ParticleSystemRenderer":
                        payload["renderer"] = {
                            "render_mode": getattr(c, "m_RenderMode", None),
                            "sort_mode": getattr(c, "m_SortMode", None),
                            "materials": [getattr(_deref(mp), "m_Name", None)
                                          for mp in (getattr(c, "m_Materials", None) or [])],
                            "min_particle_size": getattr(c, "m_MinParticleSize", None),
                            "max_particle_size": getattr(c, "m_MaxParticleSize", None),
                        }
            path = self.alloc.path(d, go_name, ".json", f"ps_{o.path_id}")
            with open(path, "w") as f:
                _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)
            by_go.setdefault(go_name, []).append(path)
            self.counts["particles"] += 1
        return by_go

    def _dump_struct(self, obj, depth=2, cap=64):
        """Serialize a nested UnityPy struct into plain JSON-able data.

        Defensive by necessity: UnityPy mixes plain objects, dict-like container
        helpers (whose ``__getattr__`` raises ``KeyError`` for dunder lookups)
        and PPtrs, so every access here is guarded. A PPtr becomes
        {"ref", "type", "name"} — a particle UV module's sprite list is exactly
        such a reference. Anything cut by `depth`/`cap` is counted, never silent.
        """
        if depth < 0:
            self.errors["dump:depth-cut"] += 1
            return "…"
        if obj is None or isinstance(obj, (int, float, str, bool)):
            return obj
        if isinstance(obj, (bytes, bytearray)):
            return f"<{len(obj)} bytes>"
        if type(obj).__name__ == "PPtr":
            if not getattr(obj, "m_PathID", 0):
                return None
            r = _reader_of(obj)
            return {"ref": oid(r), "type": r.type.name, "name": self.name_of(r)} if r is not None \
                else {"ref": None, "path_id": getattr(obj, "m_PathID", None)}
        if isinstance(obj, (list, tuple)):
            if len(obj) > cap:
                self.errors["dump:list-cut"] += 1
            return [self._dump_struct(x, depth - 1, cap) for x in list(obj)[:cap]]
        if isinstance(obj, dict):
            return {str(k): self._dump_struct(v, depth - 1, cap)
                    for k, v in list(obj.items())[:cap]}
        try:  # dict-like container helpers
            items = list(obj.items())
        except Exception:
            items = None
        if items is not None:
            return {str(k): self._dump_struct(v, depth - 1, cap) for k, v in items[:cap]}
        try:
            names = list(vars(obj).keys())
        except Exception:
            try:
                names = [n for n in dir(obj) if not n.startswith("_")]
            except Exception:
                return str(obj)
        fields = {}
        for k in names:
            if k.startswith("_") or k in ("object_reader", "read", "save", "assets_file"):
                continue
            try:
                v = getattr(obj, k)
            except Exception:
                continue
            if callable(v):
                continue
            fields[k] = self._dump_struct(v, depth - 1, cap)
        return fields if fields else str(obj)

    def export_animations(self):
        """Clips (legacy + Mecanim containers) and controllers with their TOS."""
        clip_dir = self.dir("animations", "clips")
        ctrl_dir = self.dir("animations", "controllers")
        tos = {}
        controllers, clip_owner = [], {}

        for o in self.objects:
            if o.type.name != "AnimatorController":
                continue
            ac = _read(o)
            if ac is None:
                self.errors["AnimatorController:read"] += 1
                continue
            names = {int(k): v for k, v in _items(getattr(ac, "m_TOS", None))}
            tos.update(names)
            clips = [getattr(_deref(c), "m_Name", None)
                     for c in (getattr(ac, "m_AnimationClips", None) or [])]
            ctrl = getattr(ac, "m_Controller", None)
            payload = {"name": ac.m_Name, "clips": clips,
                       "tos": {str(k): v for k, v in names.items()},
                       "layers": [], "state_machines": []}
            for lay in (getattr(ctrl, "m_LayerArray", None) or []):
                payload["layers"].append(self._dump_struct(getattr(lay, "data", lay), depth=10, cap=4096))
            for sm in (getattr(ctrl, "m_StateMachineArray", None) or []):
                payload["state_machines"].append(
                    self._dump_struct(getattr(sm, "data", sm), depth=12, cap=4096))
            path = self.alloc.path(ctrl_dir, ac.m_Name, ".json", f"controller_{o.path_id}")
            with open(path, "w") as f:
                _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)
            for c in clips:
                clip_owner[c] = ac.m_Name
            controllers.append(ac.m_Name)
            self.counts["animator_controllers"] += 1

        for o in self.objects:
            if o.type.name != "AnimationClip":
                continue
            cl = _read(o)
            if cl is None:
                self.errors["AnimationClip:read"] += 1
                continue
            payload = {"name": cl.m_Name,
                       "sample_rate": getattr(cl, "m_SampleRate", None),
                       "wrap_mode": getattr(cl, "m_WrapMode", None),
                       "legacy": getattr(cl, "m_Legacy", None),
                       "controller": clip_owner.get(cl.m_Name),
                       "events": len(getattr(cl, "m_Events", None) or []),
                       "bindings": [], "curves": {}}
            bind = getattr(cl, "m_ClipBindingConstant", None)
            for b in (getattr(bind, "genericBindings", None) or []):
                p = getattr(b, "path", None)
                payload["bindings"].append({
                    "path_hash": p, "path": tos.get(int(p)) if p is not None else None,
                    "attribute_hash": getattr(b, "attribute", None),
                    "type_id": getattr(b, "typeID", None)})
            legacy = {"position": getattr(cl, "m_PositionCurves", None) or [],
                      "rotation": getattr(cl, "m_RotationCurves", None) or [],
                      "scale": getattr(cl, "m_ScaleCurves", None) or [],
                      "euler": getattr(cl, "m_EulerCurves", None) or [],
                      "float": getattr(cl, "m_FloatCurves", None) or []}
            for kind, arr in legacy.items():
                if arr:
                    payload["curves"][kind] = [self._dump_struct(c, depth=10, cap=100000) for c in arr]
            if not payload["curves"]:
                payload["curves"] = self._decode_muscle_clip(cl, payload)
            path = self.alloc.path(clip_dir, cl.m_Name, ".json", f"clip_{o.path_id}")
            with open(path, "w") as f:
                _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)
            self.counts["animation_clips"] += 1
        return {"controllers": controllers, "tos_entries": len(tos)}

    def _decode_muscle_clip(self, clip, payload):
        """Mecanim curves live behind m_MuscleClip.m_Clip (an OffsetPtr)."""
        try:
            mc = getattr(clip, "m_MuscleClip", None)
            if mc is None:
                payload["curves_status"] = "none"
                return {}
            inner = getattr(getattr(mc, "m_Clip", None), "data", None)
            if inner is None:
                payload["curves_status"] = "partial: m_Clip could not be dereferenced"
                return {}
            out = {}
            streamed = getattr(inner, "m_StreamedClip", None)
            data = getattr(streamed, "data", None) if streamed is not None else None
            if data:
                out["streamed_frames"] = decode_streamed_clip(list(data))
            dense = getattr(inner, "m_DenseClip", None)
            if dense is not None and getattr(dense, "m_FrameCount", 0):
                out["dense"] = decode_dense_clip(dense)
            const = getattr(inner, "m_ConstantClip", None)
            cdata = getattr(const, "data", None) if const is not None else None
            if cdata:
                out["constant"] = [float(x) for x in cdata]
            payload["curves_status"] = "decoded" if out else "partial: empty containers"
            return out
        except Exception as e:  # never drop a clip silently
            payload["curves_status"] = f"partial: {type(e).__name__}: {e}"
            self.errors["AnimationClip:muscle-decode"] += 1
            return {}

    def export_physics(self, entity_names=None):
        out = {"PhysicsManager": {}, "Physics2DSettings": {}, "PhysicMaterials": {},
               "rigidbodies": []}
        for o in self.objects:
            t = o.type.name
            if t in ("PhysicsManager", "Physics2DSettings"):
                d = _read(o)
                if d is not None:
                    out[t] = self._dump_struct(d, depth=8, cap=4096)
            elif t == "PhysicMaterial":
                d = _read(o)
                if d is None:
                    continue
                out["PhysicMaterials"][d.m_Name] = {
                    "dynamicFriction": getattr(d, "m_DynamicFriction", None),
                    "staticFriction": getattr(d, "m_StaticFriction", None),
                    "bounciness": getattr(d, "m_Bounciness", None),
                    "frictionCombine": getattr(d, "m_FrictionCombine", None),
                    "bounceCombine": getattr(d, "m_BounceCombine", None)}
            elif t == "Rigidbody":
                d = _read(o)
                if d is None:
                    continue
                go = _deref(getattr(d, "m_GameObject", None))
                name = getattr(go, "m_Name", None)
                if not name:
                    continue
                comps = [_ctype(c) for c in _components(go)] if go is not None else []
                rec = dict(rigidbody_dict(d), id=oid(o), gameObject=name, gameObject_id=oid(go),
                           path=_go_path(go),
                           file=os.path.basename(o.assets_file.name or "?"))
                # a kinematic or jointed body is often a menu/showcase prop that
                # shares its name with the gameplay object — never trust the name
                if rec["isKinematic"] or any(c.endswith("Joint") for c in comps):
                    rec["display_candidate"] = True
                out["rigidbodies"].append(rec)
        dup = collections.Counter(r["gameObject"] for r in out["rigidbodies"])
        for r in out["rigidbodies"]:
            r["name_dup"] = dup[r["gameObject"]]
        self.write_json("physics.json", out)
        return out

    def export_project_settings(self):
        d = self.dir("project-settings")
        wanted = {"PhysicsManager": "physics", "Physics2DSettings": "physics2d",
                  "TimeManager": "time", "QualitySettings": "quality",
                  "GraphicsSettings": "graphics", "TagManager": "tags-and-layers",
                  "AudioManager": "audio", "InputManager": "input",
                  "RenderSettings": "render-settings", "LightmapSettings": "lightmap",
                  "NavMeshSettings": "navmesh", "BuildSettings": "build",
                  "PlayerSettings": "player"}
        written, failed = {}, []
        for o in self.objects:
            t = o.type.name
            if t not in wanted or wanted[t] in written:
                continue
            s = _read(o)
            if s is None:
                failed.append(t)
                self.errors[f"{t}:read"] += 1
                continue
            payload = self._dump_struct(s, depth=8, cap=4096)
            with open(os.path.join(d, wanted[t] + ".json"), "w") as f:
                _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)
            written[wanted[t]] = payload
            self.counts["project_settings"] += 1
        self._write_settings_readme(d, written, failed)
        if failed:
            self.notes.append(
                "Project settings that failed to parse (layout newer than UnityPy): "
                + ", ".join(sorted(set(failed)))
                + " — fall back to the APK manifest for identity fields.")
        return written

    def _write_settings_readme(self, d, written, failed):
        """Call out only the values that differ from Unity's defaults — those are
        the tuning a clone would otherwise spend days guessing."""
        defaults = {"gravity_y": -9.81, "defaultSolverIterations": 6,
                    "defaultSolverVelocityIterations": 1, "m_BounceThreshold": 2.0,
                    "m_DefaultMaxAngularSpeed": 7.0, "Fixed_Timestep": 0.02}
        notable = []
        phys = written.get("physics") or {}
        g = phys.get("m_Gravity") or {}
        gy = g.get("y") if isinstance(g, dict) else None
        if gy is not None and abs(float(gy) - defaults["gravity_y"]) > 0.01:
            notable.append(("gravity.y", gy, defaults["gravity_y"]))
        for key in ("defaultSolverIterations", "defaultSolverVelocityIterations",
                    "m_BounceThreshold", "m_DefaultMaxAngularSpeed",
                    "m_DefaultSolverIterations", "m_DefaultSolverVelocityIterations"):
            v = phys.get(key)
            base = defaults.get(key.replace("m_Default", "default"))
            if v is not None and base is not None and float(v) != float(base):
                notable.append((f"physics.{key}", v, base))
        t = written.get("time") or {}
        fts = _as_seconds(t.get("Fixed_Timestep"))
        if fts is not None and abs(fts - defaults["Fixed_Timestep"]) > 1e-6:
            notable.append(("time.Fixed_Timestep", f"{fts:g} ({1 / fts:.0f} Hz)",
                            defaults["Fixed_Timestep"]))
        lines = ["# Project settings (recovered from globalgamemanagers)", "",
                 "These are the original game's engine settings, not guesses.", ""]
        if notable:
            lines += ["## Values that differ from Unity defaults", "",
                      "| Setting | This game | Unity default |", "|---|---|---|"]
            for k, v, base in notable:
                lines.append(f"| `{k}` | **{v}** | {base} |")
            lines += ["", "Copy these into the clone's project settings before tuning "
                          "anything by hand — physics feel depends on them.", ""]
        else:
            lines += ["No sampled setting differed from the Unity defaults.", ""]
        lines += ["## Files", ""] + [f"- `{k}.json`" for k in sorted(written)]
        if failed:
            lines += ["", "## Not parsed", ""] + [f"- {f}" for f in sorted(set(failed))]
        with open(os.path.join(d, "README.md"), "w") as f:
            f.write("\n".join(lines) + "\n")

    def export_ui(self):
        """Canvas + the full RectTransform tree, so screens are reconstructable.

        Every node carries its id, its rect, and — decoded from the script values —
        what it draws: the Image's bound sprite (not a name guess), TMP text and
        size, button wiring. The canvas carries its CanvasScaler, without which
        reference numbers cannot be turned into screen pixels."""
        d = self.dir("ui")
        n = 0
        for o in self.objects:
            if o.type.name != "Canvas":
                continue
            c = _read(o)
            if c is None:
                self.errors["Canvas:read"] += 1
                continue
            go = _deref(getattr(c, "m_GameObject", None))
            if go is None:
                continue
            scaler, scaler_on = None, None
            cur = go
            for _ in range(256):            # a nested canvas is scaled by its root's scaler
                for comp in _components(cur):
                    if _ctype(comp) == "MonoBehaviour" and self.script_of(comp)[2] == "CanvasScaler":
                        scaler = _pick(self.mb_values(comp)[1], UI_SUMMARY["CanvasScaler"])
                        scaler_on = cur.m_Name
                if scaler is not None:
                    break
                ptr = _father(_transform_of(cur))
                cur = _deref(getattr(ptr, "m_GameObject", None)) if ptr is not None else None
                if cur is None:
                    break
            payload = {"name": go.m_Name, "id": oid(go), "path": _go_path(go),
                       "render_mode": getattr(c, "m_RenderMode", None),
                       "sorting_layer_id": getattr(c, "m_SortingLayerID", None),
                       "sorting_order": getattr(c, "m_SortingOrder", None),
                       "pixel_perfect": getattr(c, "m_PixelPerfect", None),
                       "plane_distance": getattr(c, "m_PlaneDistance", None),
                       "override_sorting": getattr(c, "m_OverrideSorting", None),
                       "nested": _has_canvas_ancestor(go),
                       "scaler": scaler, "scaler_on": scaler_on,
                       "tree": self._rect_tree(go, 0, set())}
            path = self.alloc.path(d, go.m_Name, ".json", f"canvas_{o.path_id}")
            with open(path, "w") as f:
                _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)
            n += 1
            self.counts["ui_canvases"] += 1
        return n

    def _rect_tree(self, go, depth, seen, max_depth=256):
        rt = _transform_of(go)
        node = {"name": go.m_Name, "id": oid(go), "active": bool(getattr(go, "m_IsActive", True)),
                "components": [], "children": []}
        for c in _components(go):
            tn = _ctype(c)
            if tn == "MonoBehaviour":
                script, fields, ok = self.mb_values(c)
                cls = script["class"] or "?"
                tn = "MB:" + cls
                summary = _pick(fields, UI_SUMMARY.get(cls)) if cls in UI_SUMMARY else None
                if summary is None and _is_graphic(fields):
                    # a game's own Graphic subclass (sliced-filled image, UI particle,
                    # Spine graphic): its colour, material and whatever art it points at
                    summary = dict(_pick(fields, ["m_Color", "m_Material", "m_RaycastTarget"]),
                                   art={k: v for k, v in fields.items() if isinstance(v, dict)
                                        and v.get("type") in ("Sprite", "Texture2D", "Material")})
                    cls = "Graphic:" + cls
                if summary is not None:
                    node.setdefault("ui", {})[cls] = summary
                node.setdefault("scripts", []).append({"class": cls, "id": oid(c), "values": ok})
            elif tn == "SpriteRenderer":
                sr = _reader_of(getattr(c, "m_Sprite", None))
                node.setdefault("ui", {})["SpriteRenderer"] = {
                    "m_Sprite": {"ref": oid(sr), "type": "Sprite", "name": self.name_of(sr)} if sr is not None else None,
                    "m_Color": _vec(getattr(c, "m_Color", None), ("r", "g", "b", "a"))}
            node["components"].append(tn)
        if rt is not None and _ctype(rt) == "RectTransform":
            node["rect"] = {
                "anchorMin": _vec(getattr(rt, "m_AnchorMin", None), ("x", "y")),
                "anchorMax": _vec(getattr(rt, "m_AnchorMax", None), ("x", "y")),
                "pivot": _vec(getattr(rt, "m_Pivot", None), ("x", "y")),
                "anchoredPosition": _vec(getattr(rt, "m_AnchoredPosition", None), ("x", "y")),
                "sizeDelta": _vec(getattr(rt, "m_SizeDelta", None), ("x", "y")),
                "localScale": _vec(getattr(rt, "m_LocalScale", None), ("x", "y", "z")),
            }
        key = oid(go)
        if key in seen or depth >= max_depth:
            self.errors["ui:tree-cut"] += 1
            return node
        seen.add(key)
        for ch in _children(go):
            if not _father_matches(ch, rt):
                self.errors["tree:father-mismatch"] += 1
            node["children"].append(self._rect_tree(ch, depth + 1, seen, max_depth))
        return node

    # -- scenes ------------------------------------------------------------
    def export_scenes(self):
        d = self.dir("scenes")
        by_file = collections.defaultdict(list)
        for o in self.objects:
            try:
                fname = os.path.basename(o.assets_file.name or "?")
            except Exception:
                fname = "?"
            by_file[fname].append(o)
        index = []
        for fname, objs in sorted(by_file.items()):
            gos = [o for o in objs if o.type.name == "GameObject"]
            if not gos or not (fname.startswith("level") or fname.startswith("globalgamemanagers")):
                continue
            roots, parented = [], set()
            trs = {}
            for o in objs:
                if o.type.name in ("Transform", "RectTransform"):
                    t = _read(o)
                    if t is None:
                        continue
                    trs[o.path_id] = t
                    for ch in getattr(t, "m_Children", None) or []:
                        try:
                            parented.add(ch.path_id)
                        except Exception:
                            pass
            for pid, t in trs.items():
                if pid not in parented:
                    g = _deref(getattr(t, "m_GameObject", None))
                    if g is not None:
                        roots.append(g)
            lines = [f"=== {fname} ({len(gos)} GameObjects) ==="]
            for r in roots:
                self._tree_lines(r, 0, lines)
            with open(os.path.join(d, f"{fname}.tree.txt"), "w") as f:
                f.write("\n".join(lines) + "\n")
            index.append({"file": fname, "gameobjects": len(gos), "roots": len(roots),
                          "root_names": [r.m_Name for r in roots]})
            self._scene_objects(fname, objs, d)
            self.counts["scenes"] += 1
        self.write_json("scenes/scenes.json", index)
        return index

    def _tree_lines(self, go, depth, lines, max_depth=256):
        comps = []
        for c in _components(go):
            tn = _ctype(c)
            if tn in ("Transform", "RectTransform"):
                continue
            comps.append("MB:" + (self.script_of(c)[2] or "?") if tn == "MonoBehaviour" else tn)
        lines.append("  " * depth + f"- {go.m_Name}  [{', '.join(comps)}]  #{oid(go)}")
        if depth >= max_depth:
            self.errors["scene:tree-cut"] += 1
            return
        for ch in _children(go):
            self._tree_lines(ch, depth + 1, lines, max_depth)

    def _scene_objects(self, fname, objs, d):
        payload = {"lights": [], "cameras": [], "audio_sources": [], "render_settings": None,
                   "transforms": []}
        # every GameObject of the scene with its world placement: level content is
        # often spawned under a scene anchor (a spawn-point object), and rebuilding a
        # level means composing with it
        for o in objs:
            if o.type.name not in ("Transform", "RectTransform"):
                continue
            t = _read(o)
            go = _deref(getattr(t, "m_GameObject", None)) if t is not None else None
            if go is None:
                continue
            payload["transforms"].append(dict({"id": oid(go), "path": _go_path(go)}, **_world_trs(t)))
        for o in objs:
            t = o.type.name
            if t == "Light":
                l = _read(o)
                if l is None:
                    continue
                payload["lights"].append({
                    **_placed(l),
                    "type": getattr(l, "m_Type", None),
                    "color": _vec(getattr(l, "m_Color", None), ("r", "g", "b", "a")),
                    "intensity": getattr(l, "m_Intensity", None),
                    "range": getattr(l, "m_Range", None),
                    "shadows": self._dump_struct(getattr(l, "m_Shadows", None), depth=1)})
            elif t == "Camera":
                c = _read(o)
                if c is None:
                    continue
                payload["cameras"].append({
                    **_placed(c),
                    "orthographic": getattr(c, "orthographic", None),
                    "orthographic_size": getattr(c, "orthographic_size", None),
                    "fov": getattr(c, "field_of_view", None),
                    "near": getattr(c, "near_clip_plane", None),
                    "far": getattr(c, "far_clip_plane", None),
                    "clear_flags": getattr(c, "m_ClearFlags", None),
                    "depth": getattr(c, "m_Depth", None),
                    "culling_mask": self._dump_struct(getattr(c, "m_CullingMask", None), depth=1)})
            elif t == "AudioSource":
                a = _read(o)
                if a is None:
                    continue
                payload["audio_sources"].append({
                    "clip": getattr(_deref(getattr(a, "m_audioClip", None)), "m_Name", None),
                    "volume": getattr(a, "m_Volume", None),
                    "loop": getattr(a, "m_Loop", None),
                    "play_on_awake": getattr(a, "m_PlayOnAwake", None)})
            elif t == "RenderSettings" and payload["render_settings"] is None:
                r = _read(o)
                if r is not None:
                    payload["render_settings"] = self._dump_struct(r, depth=6)
        with open(os.path.join(d, f"{fname}.objects.json"), "w") as f:
            _dump_json(payload, f, indent=1, ensure_ascii=False, default=str)

    # -- structural entity discovery ---------------------------------------
    def discover_prefab_roots(self, max_depth=4):
        """Root GameObjects that carry renderable content — engine-level, so it
        works for any game regardless of naming conventions.

        A prefab asset is a transform hierarchy whose root has no parent and
        which lives outside a scene file. Name-based discovery cannot find these
        when a game exports meshes as `BezierCurve.041`; this can.
        """
        parented, trs = set(), {}
        for o in self.objects:
            if o.type.name not in ("Transform", "RectTransform"):
                continue
            t = _read(o)
            if t is None:
                continue
            try:
                fname = os.path.basename(o.assets_file.name or "?")
            except Exception:
                fname = "?"
            trs[(fname, o.path_id)] = (t, fname)
            for ch in getattr(t, "m_Children", None) or []:
                try:
                    parented.add((fname, ch.path_id))
                except Exception:
                    pass

        content = ("MeshFilter", "SkinnedMeshRenderer", "SpriteRenderer",
                   "MeshRenderer", "ParticleSystem", "TrailRenderer", "LineRenderer")

        def bears_content(go, depth=0):
            if depth > max_depth:
                return False
            for c in _components(go):
                if _ctype(c) in content:
                    return True
            for ch in _children(go):
                if bears_content(ch, depth + 1):
                    return True
            return False

        prefabs, scene_roots = set(), set()
        for key, (t, fname) in trs.items():
            if key in parented:
                continue
            g = _deref(getattr(t, "m_GameObject", None))
            if g is None or not g.m_Name or not bears_content(g):
                continue
            (scene_roots if fname.startswith("level") else prefabs).add(g.m_Name)
        return prefabs, scene_roots

    # -- architecture ------------------------------------------------------
    def export_architecture(self):
        """MonoScript inventory — the full C# class list, no IL2CPP tooling."""
        by_asm = collections.defaultdict(set)
        for o in self.objects:
            if o.type.name != "MonoScript":
                continue
            s = _read(o)
            if s is None:
                continue
            asm = (getattr(s, "m_AssemblyName", "") or "unknown").replace(".dll", "")
            ns = getattr(s, "m_Namespace", "") or ""
            cn = getattr(s, "m_ClassName", "") or ""
            if cn:
                by_asm[asm].add(f"{ns}.{cn}" if ns else cn)
        lines = ["# Architecture — C# class inventory", "",
                 "Recovered from `MonoScript` records; no IL2CPP tooling required.",
                 "Field values of every MonoBehaviour are decoded separately into `scripts/`",
                 "(type trees rebuilt from libil2cpp.so + global-metadata.dat).", ""]
        engine_prefixes = ("Unity", "System", "mscorlib", "netstandard", "Mono", "TextMesh")
        game = {k: v for k, v in by_asm.items() if not k.startswith(engine_prefixes)}
        for asm in sorted(game, key=lambda a: -len(game[a])):
            classes = sorted(game[asm])
            lines.append(f"## `{asm}` — {len(classes)} types")
            lines.append("")
            grouped = collections.defaultdict(list)
            for c in classes:
                grouped[c.rsplit(".", 1)[0] if "." in c else "(root)"].append(c)
            for ns in sorted(grouped):
                lines.append(f"**{ns}** — " + ", ".join(f"`{c.rsplit('.', 1)[-1]}`"
                                                        for c in sorted(grouped[ns])))
            lines.append("")
        engine = {k: len(v) for k, v in by_asm.items() if k.startswith(engine_prefixes)}
        if engine:
            lines += ["## Engine / package assemblies (counts only)", "",
                      ", ".join(f"`{k}` ({v})" for k, v in sorted(engine.items())), ""]
        with open(os.path.join(self.out, "ARCHITECTURE.md"), "w") as f:
            f.write("\n".join(lines))
        return {k: len(v) for k, v in by_asm.items()}


def _as_seconds(value):
    """Unity 6 stores some durations as a RationalTime struct, not a float."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict):
        count = value.get("m_Count")
        rate = value.get("m_Rate") or {}
        num = rate.get("m_Numerator") if isinstance(rate, dict) else None
        den = rate.get("m_Denominator") if isinstance(rate, dict) else None
        try:
            if count is not None and num:
                return float(count) / (float(num) / float(den or 1))
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


def rigidbody_dict(rb):
    return {"mass": getattr(rb, "m_Mass", None), "drag": getattr(rb, "m_Drag", None),
            "angularDrag": getattr(rb, "m_AngularDrag", None),
            "useGravity": bool(getattr(rb, "m_UseGravity", False)),
            "isKinematic": bool(getattr(rb, "m_IsKinematic", False)),
            "interpolate": getattr(rb, "m_Interpolate", None),
            "collisionDetection": getattr(rb, "m_CollisionDetection", None),
            "constraints": getattr(rb, "m_Constraints", None)}


# ---------------------------------------------------------------------------
# Entity grouping — "things that combine into one object share a folder"
# ---------------------------------------------------------------------------

def collect_entity_names(levels, extractor, extra=None, limit=2000):
    """Which root GameObjects deserve their own folder.

    Sources, in order of reliability:
    1. **structural** — every content-bearing prefab root in the package. Engine
       level, so it works for any game; a title whose meshes are called
       `BezierCurve.041` is grouped just as well as one with semantic names.
    2. **level data** — every distinct entity id the level database names.
    3. **name hints** — a gameplay-noun sweep, which catches objects embedded in
       a scene rather than shipped as prefabs (a cannon parented under the
       gameplay scene root, say), minus obvious UI names.
    4. explicit extras from the caller.
    """
    from_levels = set()
    for variants in levels.values():
        for lv in variants:
            for e in (lv.get("Entities") or []):
                i = e.get("Id") or e.get("id") or e.get("name")
                if i:
                    from_levels.add(str(i))
    go_names = set()
    for o in extractor.objects:
        if o.type.name != "GameObject":
            continue
        g = _read(o)
        if g is not None and g.m_Name:
            go_names.add(g.m_Name)
    prefabs, scene_roots = extractor.discover_prefab_roots()
    hinted = {n for n in go_names
              if ENTITY_HINT_RE.search(n) and not UI_NOISE_RE.search(n)}
    wanted = (prefabs | scene_roots | from_levels | hinted | set(extra or [])) & go_names
    dropped_for_limit = 0
    if limit and len(wanted) > limit:
        keep = (from_levels & go_names) | set(sorted(prefabs)[:limit])
        dropped_for_limit = len(wanted) - len(keep)
        wanted = keep
    return wanted, {"from_levels": len(from_levels),
                    "matched_in_package": len(from_levels & go_names),
                    "prefab_roots": len(prefabs),
                    "scene_roots": len(scene_roots),
                    "hinted": len(hinted),
                    "dropped_for_limit": dropped_for_limit,
                    "named_by_levels": sorted(from_levels & go_names)}


class EntityBuilder:
    def __init__(self, extractor, wanted, levels_stats, particles_by_go):
        self.x = extractor
        self.wanted = wanted
        self.levels_stats = levels_stats or {}
        self.particles = particles_by_go or {}
        self.entities = {}

    def build(self):
        for o in self.x.objects:
            if o.type.name != "GameObject":
                continue
            g = _read(o)
            if g is None or g.m_Name not in self.wanted or g.m_Name in self.entities:
                continue
            self.entities[g.m_Name] = self._walk(g)
        return self.entities

    def _walk(self, root, max_nodes=20000):
        agg = {"name": root.m_Name, "id": oid(root), "path": _go_path(root),
               "meshes": [], "broken_pieces": [], "materials": {},
               "textures": {}, "colliders": [], "joints": [], "rigidbody": None,
               "animator": None, "particles": [], "particle_owners": [], "sprites": [],
               "scripts": set(), "children": [], "external_meshes": [], "transform": None,
               "renderers": [], "nodes": []}
        tr = _transform_of(root)
        if tr is not None:
            agg["transform"] = {
                "localPosition": _vec(getattr(tr, "m_LocalPosition", None), ("x", "y", "z")),
                "localScale": _vec(getattr(tr, "m_LocalScale", None), ("x", "y", "z")),
                "localRotation": _vec(getattr(tr, "m_LocalRotation", None))}
        agg["nodes"] = self._node_tree(root, max_nodes)
        for n in agg["nodes"]:
            go = n.pop("_go")
            self._collect(go, agg, is_root=n["parent"] < 0)
            if n["parent"] >= 0:
                agg["children"].append(n["name"])
        agg["scripts"] = sorted(agg["scripts"])
        agg["children"] = sorted(set(agg["children"]))
        # child GameObjects own their own ParticleSystems; pull every one in the
        # subtree, not just a system sitting on the root
        for owner in dict.fromkeys([root.m_Name] + agg["particle_owners"]):
            for ps in self.particles.get(owner, []):
                name = os.path.basename(ps)
                if name not in agg["particles"]:
                    agg["particles"].append(name)
        return agg

    def _node_tree(self, root, max_nodes=20000):
        """The prefab's real hierarchy: one entry per GameObject in DEPTH-FIRST order
        (a child always directly follows its parent's subtree start, so the list
        reads as the tree), with its id, parent index + name, full path, local
        transform, the mesh it carries (by id) and its materials IN SLOT ORDER.

        Breadth-first order made a reader take the previous line as the parent —
        a clone project hung a lock's shackle under the wrong node that way."""
        nodes, stack, seen = [], [(root, -1, 0, getattr(root, "m_Name", "?"))], set()
        while stack and len(nodes) < max_nodes:
            go, parent, depth, path = stack.pop()
            key = oid(go)
            if key in seen:
                self.x.errors["entity:cycle"] += 1
                continue
            seen.add(key)
            idx = len(nodes)
            n = {"name": go.m_Name, "id": key, "parent": parent,
                 "parent_name": nodes[parent]["name"] if parent >= 0 else None,
                 "path": path, "depth": depth,
                 "active": bool(getattr(go, "m_IsActive", True)),
                 "components": [], "mesh": None, "mesh_id": None, "materials": [],
                 "material_ids": [], "sprite": None, "sprite_id": None, "particle": False,
                 "_go": go}
            tr = _transform_of(go)
            if tr is not None:
                n["localPosition"] = _vec(getattr(tr, "m_LocalPosition", None), ("x", "y", "z"))
                n["localRotation"] = _vec(getattr(tr, "m_LocalRotation", None))
                n["localScale"] = _vec(getattr(tr, "m_LocalScale", None), ("x", "y", "z"))
            for c in _components(go):
                tn = _ctype(c)
                if tn == "MonoBehaviour":
                    cls = self.x.script_of(c)[2] or "?"
                    n["components"].append("MB:" + cls)
                    n.setdefault("scripts", []).append({"class": cls, "id": oid(c)})
                    continue
                n["components"].append(tn)
                if tn == "SkinnedMeshRenderer":
                    bones = []
                    for bp in (getattr(c, "m_Bones", None) or []):
                        bt = _deref(bp)
                        bg = _reader_of(getattr(bt, "m_GameObject", None)) if bt is not None else None
                        bones.append(oid(bg) if bg is not None else None)
                    n["bones"] = bones
                if tn in ("MeshFilter", "SkinnedMeshRenderer"):
                    mr = _reader_of(getattr(c, "m_Mesh", None))
                    mname, kind = _mesh_ref(c, self.x.externals_of)
                    if mname and not kind:
                        n["mesh"], n["mesh_id"] = mname, oid(mr) if mr is not None else None
                    elif kind:
                        n["mesh"] = f"<{kind}>"
                        if kind.startswith("builtin:"):
                            pid = getattr(getattr(c, "m_Mesh", None), "m_PathID", None)
                            n["builtin_mesh"] = BUILTIN_MESHES.get(pid, f"unknown:{pid}")
                if tn in ("MeshRenderer", "SkinnedMeshRenderer", "SpriteRenderer",
                          "ParticleSystemRenderer"):
                    for mp in (getattr(c, "m_Materials", None) or []):
                        r = _reader_of(mp)
                        m = _read(r) if r is not None else None
                        n["materials"].append(m.m_Name if m is not None and m.m_Name else None)
                        n["material_ids"].append(oid(r) if r is not None else None)
                if tn == "SpriteRenderer":
                    sr = _reader_of(getattr(c, "m_Sprite", None))
                    sp = _read(sr) if sr is not None else None
                    if sp is not None and sp.m_Name:
                        n["sprite"], n["sprite_id"] = sp.m_Name, oid(sr)
                        src = self.x.sprite_files.get(oid(sr))
                        n["sprite_file"] = os.path.basename(src) if src else None
                        pv = _vec(getattr(sp, "m_Pivot", None), ("x", "y"))
                        n["sprite_ppu"] = float(getattr(sp, "m_PixelsToUnits", 100) or 100)
                        n["sprite_pivot"] = pv
                        n["sprite_color"] = _vec(getattr(c, "m_Color", None), ("r", "g", "b", "a"))
                if tn == "Rigidbody":
                    n["rigidbody"] = rigidbody_dict(c)
                if tn.endswith("Collider"):
                    cd = collider_dict(c, tn)
                    if tn == "MeshCollider":
                        cm = _reader_of(getattr(c, "m_Mesh", None))
                        src = self.x.mesh_files.get(oid(cm)) if cm is not None else None
                        cd["mesh_file"] = os.path.basename(src) if src else None
                    n.setdefault("colliders", []).append(cd)
                if tn.endswith("Joint"):
                    n.setdefault("joints", []).append(joint_dict(c, tn))
                if tn == "ParticleSystem":
                    n["particle"] = True
            if n["mesh_id"] in self.x.mesh_index:
                n["submeshes"] = self.x.mesh_index[n["mesh_id"]]["submeshes"]
                if n["materials"] and len(n["materials"]) != n["submeshes"]:
                    # more slots than sub-meshes: Unity draws the last sub-mesh again
                    # with each extra material; fewer: the rest is not drawn
                    n["slot_mismatch"] = [len(n["materials"]), n["submeshes"]]
            nodes.append(n)
            kids = _children(go)
            for ch in kids:
                if not _father_matches(ch, tr):
                    self.x.errors["tree:father-mismatch"] += 1
            for ch in reversed(kids):     # reversed: the stack pops them in order
                stack.append((ch, idx, depth + 1, f"{path}/{getattr(ch, 'm_Name', '?')}"))
        if stack:
            self.x.errors["entity:node-cap"] += 1
        # debris: own name says so, or an ancestor does
        for n in nodes:
            anc, cur = [], n["parent"]
            while cur >= 0:
                anc.append(nodes[cur]["name"])
                cur = nodes[cur]["parent"]
            n["fracture"] = bool(
                (n["mesh"] and classify_mesh(n["mesh"]) == "broken")
                or FRACTURE_PARENT_RE.search(n["name"] or "")
                or any(FRACTURE_PARENT_RE.search(a or "") for a in anc))
        return nodes

    def _collect(self, go, agg, is_root=False):
        for c in _components(go):
            tn = _ctype(c)
            if tn in ("MeshFilter", "SkinnedMeshRenderer", "MeshCollider"):
                name, kind = _mesh_ref(c, self.x.externals_of)
                mr = _reader_of(getattr(c, "m_Mesh", None))
                if kind:
                    if kind not in agg["external_meshes"]:
                        agg["external_meshes"].append(kind)
                elif name and mr is not None:
                    bucket = "broken_pieces" if classify_mesh(name) == "broken" else "meshes"
                    if oid(mr) not in agg[bucket]:
                        agg[bucket].append(oid(mr))
            if tn in ("MeshRenderer", "SkinnedMeshRenderer", "SpriteRenderer",
                      "ParticleSystemRenderer", "TrailRenderer", "LineRenderer"):
                agg["renderers"].append(tn)
                for mp in (getattr(c, "m_Materials", None) or []):
                    r = _reader_of(mp)
                    m = _read(r) if r is not None else None
                    if m is None or not m.m_Name:
                        continue
                    sp = getattr(m, "m_SavedProperties", None)
                    slots, slot_ids = {}, {}
                    for k, v in _items(getattr(sp, "m_TexEnvs", None)):
                        tr = _reader_of(getattr(v, "m_Texture", None))
                        tex = _read(tr) if tr is not None else None
                        if tex is not None and getattr(tex, "m_Name", None):
                            slots[k], slot_ids[k] = tex.m_Name, oid(tr)
                            agg["textures"][oid(tr)] = k
                    agg["materials"].setdefault(oid(r), {
                        "name": m.m_Name,
                        "keywords": list(getattr(m, "m_ValidKeywords", None) or []),
                        "texture_slots": slots, "texture_ids": slot_ids,
                        "floats": {k: round(float(v), 5)
                                   for k, v in _items(getattr(sp, "m_Floats", None))},
                        "colors": {k: [round(float(getattr(col, ch, 0.0)), 4)
                                       for ch in ("r", "g", "b", "a")]
                                   for k, col in _items(getattr(sp, "m_Colors", None))}})
                if tn == "SpriteRenderer":
                    s = _deref(getattr(c, "m_Sprite", None))
                    if s is not None and s.m_Name:
                        agg["sprites"].append(s.m_Name)
            elif tn.endswith("Collider"):
                agg["colliders"].append(dict(collider_dict(c, tn), node=go.m_Name))
            elif tn.endswith("Joint"):
                agg["joints"].append(dict(joint_dict(c, tn), node=go.m_Name))
            elif tn == "ParticleSystem":
                agg["particle_owners"].append(go.m_Name)
            elif tn == "Rigidbody" and (is_root or agg["rigidbody"] is None):
                # the root's own body wins; a child's only stands in when the root has none
                agg["rigidbody"] = dict(rigidbody_dict(c), node=go.m_Name)
            elif tn == "Animator" and agg["animator"] is None:
                ctrl = _deref(getattr(c, "m_Controller", None))
                agg["animator"] = {
                    "controller": getattr(ctrl, "m_Name", None) if ctrl else None,
                    "applyRootMotion": getattr(c, "m_ApplyRootMotion", None),
                    "cullingMode": getattr(c, "m_CullingMode", None),
                    "updateMode": getattr(c, "m_UpdateMode", None)}
            elif tn == "MonoBehaviour":
                n = self.x.script_of(c)[2]
                if n:
                    agg["scripts"].add(n)


def prune_entities(entities, named_by_levels):
    """Drop pattern-matched candidates that turned out to be empty UI objects.

    Anything the level data names is always kept — its absence of geometry is
    itself a finding. Everything else has to earn its folder with real content.
    """
    kept, dropped = {}, []
    for name, agg in entities.items():
        procedural = any(re.search(r"tube|rope|generator|verlet|procedural|spline", s_, re.I)
                         for s_ in agg["scripts"])
        substantive = bool(agg["meshes"] or agg["broken_pieces"] or agg["colliders"]
                           or agg["joints"] or agg["particles"] or agg["sprites"]
                           or procedural
                           or any(k.startswith("builtin:") for k in agg["external_meshes"]))
        if name in named_by_levels or substantive:
            kept[name] = agg
        else:
            dropped.append(name)
    return kept, dropped


def collider_dict(c, type_name):
    mat = _deref(getattr(c, "m_Material", None))
    d = {"type": type_name,
         "isTrigger": bool(getattr(c, "m_IsTrigger", False)),
         "physicMaterial": getattr(mat, "m_Name", None) if mat else None,
         "center": _vec(getattr(c, "m_Center", None), ("x", "y", "z"))}
    if type_name == "BoxCollider":
        d["size"] = _vec(getattr(c, "m_Size", None), ("x", "y", "z"))
    elif type_name == "SphereCollider":
        d["radius"] = getattr(c, "m_Radius", None)
    elif type_name == "CapsuleCollider":
        d["radius"] = getattr(c, "m_Radius", None)
        d["height"] = getattr(c, "m_Height", None)
        d["direction"] = getattr(c, "m_Direction", None)
    elif type_name == "MeshCollider":
        mesh = _deref(getattr(c, "m_Mesh", None))
        d["mesh"] = getattr(mesh, "m_Name", None) if mesh else None
        d["convex"] = bool(getattr(c, "m_Convex", False))
        d["cookingOptions"] = getattr(c, "m_CookingOptions", None)
        d["inflateMesh"] = getattr(c, "m_InflateMesh", None)
        d["skinWidth"] = getattr(c, "m_SkinWidth", None)
    return d


def joint_dict(j, type_name):
    body = _deref(getattr(j, "m_ConnectedBody", None))
    connected = None
    if body is not None:
        go = _deref(getattr(body, "m_GameObject", None))
        connected = getattr(go, "m_Name", None) if go else None
    d = {"type": type_name, "connectedBody": connected,
         "anchor": _vec(getattr(j, "m_Anchor", None), ("x", "y", "z")),
         "axis": _vec(getattr(j, "m_Axis", None), ("x", "y", "z")),
         "breakForce": getattr(j, "m_BreakForce", None),
         "breakTorque": getattr(j, "m_BreakTorque", None),
         "enableCollision": getattr(j, "m_EnableCollision", None)}
    for k in ("m_XMotion", "m_YMotion", "m_ZMotion", "m_AngularXMotion",
              "m_AngularYMotion", "m_AngularZMotion", "m_ConfiguredInWorldSpace",
              "m_AutoConfigureConnectedAnchor", "m_Spring", "m_Damper", "m_Distance"):
        v = getattr(j, k, None)
        if v is not None and isinstance(v, (int, float, bool)):
            d[k.lstrip("m_")] = v
    return d


# ---------------------------------------------------------------------------
# Level analysis
# ---------------------------------------------------------------------------

def analyse_levels(levels):
    """Derive the design curve from the level database.

    The single most transferable artifact in the whole extraction: which
    mechanic is introduced at which level, how much of each entity is used,
    and whether the build ships parallel A/B ladders.
    """
    if not levels:
        return {"levels": 0}
    ids = sorted(levels)
    counts, first_seen = collections.Counter(), {}
    numeric = collections.defaultdict(list)
    schema = set()
    for lid in ids:
        lv = levels[lid][0]
        schema.update(lv.keys())
        for k, v in lv.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numeric[k].append(v)
        ents = lv.get("Entities") or []
        numeric["_entities_per_level"].append(len(ents))
        for e in ents:
            i = e.get("Id") or e.get("id") or e.get("name")
            if not i:
                continue
            counts[str(i)] += 1
            first_seen.setdefault(str(i), lid)
    families = {}
    for i, lid in first_seen.items():
        fam = re.sub(r"[_\d].*$", "", i) or i
        families[fam] = min(families.get(fam, 10 ** 9), lid)
    stats = {}
    for k, vals in numeric.items():
        if vals:
            stats[k] = {"min": min(vals), "max": max(vals),
                        "avg": round(sum(vals) / len(vals), 3)}
    return {"levels": len(ids), "id_range": [ids[0], ids[-1]],
            "schema_keys": sorted(schema),
            "distinct_entities": len(counts),
            "numeric_stats": stats,
            "entity_usage": dict(counts.most_common()),
            "entity_first_level": dict(sorted(first_seen.items(), key=lambda x: x[1])),
            "mechanic_introduction_order": [
                {"level": lid, "family": fam}
                for fam, lid in sorted(families.items(), key=lambda x: x[1])],
            "ab_variants": level_duplicate_report(levels)}


# ---------------------------------------------------------------------------
# Emitters — self-contained entity folders
# ---------------------------------------------------------------------------

def write_entity_folders(x, entities, level_analysis, particles_by_go):
    """One folder per entity holding everything needed to rebuild it."""
    root = x.dir("entities")
    usage = (level_analysis or {}).get("entity_usage", {})
    first = (level_analysis or {}).get("entity_first_level", {})
    index = []
    for name, agg in sorted(entities.items()):
        d = os.path.join(root, safe_name(name, "entity"))
        os.makedirs(d, exist_ok=True)
        td = os.path.join(d, "textures")
        copied_tex, tex_file = {}, {}
        if agg["textures"]:
            os.makedirs(td, exist_ok=True)
            for tex_id, slot in agg["textures"].items():
                src = x.texture_files.get(tex_id)
                if not src or not os.path.exists(src):
                    continue
                dst = os.path.join(td, os.path.basename(src))
                if not os.path.exists(dst):
                    _link_or_copy(src, dst)
                tex_file[tex_id] = os.path.join("textures", os.path.basename(dst))
                copied_tex.setdefault(slot, tex_file[tex_id])
        # one .mtl with EVERY material, each under a name unique in this entity
        # (two materials may share a name; the id tells them apart)
        mtl_name, used = {}, collections.Counter()
        for mid, md in agg["materials"].items():
            base = safe_name(md.get("name"), "material")
            used[base] += 1
            mtl_name[mid] = base if used[base] == 1 else f"{base}__{used[base]}"
        mtl_file = None
        if agg["materials"]:
            mtl_file = "materials.mtl"
            with open(os.path.join(d, mtl_file), "w") as f:
                for mid, md in agg["materials"].items():
                    tex = {k: tex_file[t] for k, t in (md.get("texture_ids") or {}).items()
                           if t in tex_file}
                    md["texture_files"] = tex       # slot -> textures/<file>, for importers
                    f.write(mtl_text(mtl_name[mid], tex, md.get("colors"), md.get("floats")))
                    f.write("\n")
        # each mesh gets the materials of the node that carries it, slot by slot
        mesh_mat, conflicts = {}, []
        for n in agg.get("nodes") or []:
            n["materials_mtl"] = [mtl_name.get(m) for m in n.get("material_ids") or []]
        for n in agg.get("nodes") or []:
            if n.get("mesh_id") and n.get("material_ids"):
                slots = [mtl_name.get(m) for m in n["material_ids"]]
                if n["mesh_id"] in mesh_mat and mesh_mat[n["mesh_id"]] != slots:
                    conflicts.append(n["path"])
                mesh_mat.setdefault(n["mesh_id"], slots)
        first_mat = next(iter(mtl_name.values()), None)
        baked = bake_skinned_nodes(x, agg.get("nodes") or [])
        whole_files = _copy_meshes(x, agg["meshes"], d, mtl_file, first_mat, mesh_mat, baked)
        broken_files = []
        if agg["broken_pieces"]:
            bd = os.path.join(d, "broken")
            os.makedirs(bd, exist_ok=True)
            # debris gets its material as well; the .mtl sits one level up
            broken_files = _copy_meshes(
                x, agg["broken_pieces"], bd,
                os.path.join("..", mtl_file) if mtl_file else None,
                first_mat, mesh_mat, baked)
        sprite_nodes = [n for n in agg.get("nodes") or [] if n.get("sprite_id") in x.sprite_files]
        if sprite_nodes:
            sd = os.path.join(d, "sprites")
            os.makedirs(sd, exist_ok=True)
            for n in sprite_nodes:
                dst = os.path.join(sd, os.path.basename(x.sprite_files[n["sprite_id"]]))
                if not os.path.exists(dst):
                    _link_or_copy(x.sprite_files[n["sprite_id"]], dst)
        anim_files = _copy_animations(x, agg, d)
        part_files = _copy_particles(x, agg, d)
        mesh_name = lambda mid: (x.mesh_index.get(mid) or {}).get("name", mid)
        info = {
            "entity": name,
            "id": agg.get("id"),
            "path": agg.get("path"),
            "levels_used": usage.get(name),
            "first_level": first.get(name),
            "transform": agg["transform"],
            "whole_meshes": [mesh_name(m) for m in agg["meshes"]],
            "whole_mesh_ids": agg["meshes"],
            "whole_mesh_files": whole_files,
            "broken_pieces": [mesh_name(m) for m in agg["broken_pieces"]],
            "broken_piece_ids": agg["broken_pieces"],
            "broken_piece_files": broken_files,
            "external_meshes": agg["external_meshes"],
            "materials": {mtl_name[mid]: dict(md, id=mid) for mid, md in agg["materials"].items()},
            "texture_slots": copied_tex,
            "mtl": mtl_file,
            "mesh_material_conflicts": conflicts,
            "colliders": agg["colliders"],
            "joints": agg["joints"],
            "rigidbody": agg["rigidbody"],
            "animator": agg["animator"],
            "animations": anim_files,
            "particles": part_files,
            "sprites": agg["sprites"],
            "renderers": sorted(set(agg["renderers"])),
            "scripts": agg["scripts"],
            "children": agg["children"],
            "nodes": _resolve_node_files(agg.get("nodes") or [], x),
            "geometry_status": _geometry_status(agg),
        }
        with open(os.path.join(d, "entity.json"), "w") as f:
            _dump_json(info, f, indent=1, ensure_ascii=False, default=str)
        with open(os.path.join(d, "README.md"), "w") as f:
            f.write(_entity_readme(info))
        with open(os.path.join(d, "nodes.tree.txt"), "w") as f:
            f.write(node_tree_text(info["nodes"]))
        index.append(info)
        x.counts["entities"] += 1
    with open(os.path.join(root, "_index.json"), "w") as f:
        _dump_json(index, f, indent=1, ensure_ascii=False, default=str)
    return index


def node_tree_text(nodes):
    """The node list as an indented tree a person reads: parent above, children
    indented under it, mesh and slot-ordered materials on the same line."""
    out = []
    for n in nodes:
        bits = []
        if n.get("mesh"):
            bits.append(f"mesh={n['mesh']}" + (f" ({n['submeshes']} sub)" if n.get("submeshes") else ""))
        if n.get("materials"):
            bits.append("mat=[" + ", ".join(str(m) for m in n["materials"]) + "]")
        if n.get("sprite"):
            bits.append(f"sprite={n['sprite']}")
        if n.get("rigidbody"):
            bits.append(f"rb={n['rigidbody'].get('mass')}kg" + (" kinematic" if n['rigidbody'].get('isKinematic') else ""))
        if n.get("fracture"):
            bits.append("debris")
        if not n.get("active", True):
            bits.append("inactive")
        out.append("  " * n.get("depth", 0) + f"- {n['name']}" + (f"  [{'; '.join(bits)}]" if bits else ""))
    return "\n".join(out) + "\n"


def _link_or_copy(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _resolve_node_files(nodes, x):
    """Attach the on-disk OBJ filename to each node that carries a mesh, so the
    tree is directly actionable: node -> file -> material slot."""
    for n in nodes:
        mid = n.get("mesh_id")
        if not mid:
            continue
        src = x.mesh_files.get(mid)
        n["mesh_file"] = os.path.basename(src) if src else None
    return nodes


def _skin_of(mesh):
    """(bindposes 4x4[], bone indices [n,4], weights [n,4]) of a skinned mesh, or None."""
    try:
        from UnityPy.helpers.MeshHelper import MeshHandler
        import numpy as np
    except Exception:
        return None
    binds = getattr(mesh, "m_BindPose", None) or []
    if not binds:
        return None
    try:
        h = MeshHandler(mesh)
        h.process()
    except Exception:
        return None
    n = len(h.m_Vertices or [])
    if not h.m_BoneIndices or len(h.m_BoneIndices) != n:
        return None
    bi = np.array([tuple(t) if isinstance(t, (list, tuple)) else (t,) for t in h.m_BoneIndices], dtype=np.int64)
    if h.m_BoneWeights is None:
        # one influence per vertex: Unity stores only the index, the weight is 1
        bw = np.zeros(bi.shape, dtype=np.float64)
        bw[:, 0] = 1.0
    else:
        if len(h.m_BoneWeights) != n:
            return None
        bw = np.array([tuple(t) if isinstance(t, (list, tuple)) else (t,) for t in h.m_BoneWeights], dtype=np.float64)
        if bw.shape[1] < bi.shape[1]:       # weights for the first k influences only
            bw = np.concatenate([bw, np.zeros((n, bi.shape[1] - bw.shape[1]))], axis=1)
        bi = bi[:, :bw.shape[1]]
    P = np.array([[[getattr(b, f"e{r}{c}") for c in range(4)] for r in range(4)] for b in binds], dtype=np.float64)
    return P, bi, bw


def _trs_matrix(n):
    import numpy as np
    x, y, z, w = n.get("localRotation") or [0, 0, 0, 1]
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4)
    M[:3, :3] = R * np.array(n.get("localScale") or [1, 1, 1])[None, :]
    M[:3, 3] = n.get("localPosition") or [0, 0, 0]
    return M


def bake_skinned_nodes(x, nodes):
    """Pose every skinned mesh by its skeleton, as Unity draws it, and express the
    result in the renderer node's own space: v' = W_node^-1 * sum_i w_i * W_bone_i * P_i * v.

    A SkinnedMeshRenderer's vertices are in bind space, not node space; drawn
    as a plain mesh at the node they land wherever the node happens to be (a
    launcher body hung mid-air in front of the level instead of resting on its
    wheels). Bone transforms are the prefab's saved pose. Returns mesh id ->
    posed OBJ text; nodes get `skin_baked` true/false (+ reason)."""
    if not x.skins:
        return {}
    import numpy as np
    world, idx = {}, {n["id"]: i for i, n in enumerate(nodes)}

    def W(i):
        if i not in world:
            p = nodes[i]["parent"]
            world[i] = (W(p) if p >= 0 else np.eye(4)) @ _trs_matrix(nodes[i])
        return world[i]

    out = {}
    for i, n in enumerate(nodes):
        mid, bones = n.get("mesh_id"), n.get("bones")
        if not mid or bones is None or mid not in x.skins:
            continue
        P, bi, bw = x.skins[mid]
        missing = [b for b in bones if b not in idx]
        if missing or len(bones) < len(P):
            n["skin_baked"], n["skin_note"] = False, f"{len(missing)} bone(s) outside this object"
            continue
        if mid in out:
            n["skin_baked"], n["skin_note"] = False, "mesh shared by two skinned nodes; first pose kept"
            continue
        inv = np.linalg.inv(W(i))
        B = np.stack([inv @ W(idx[b]) @ P[k] for k, b in enumerate(bones[:len(P)])])     # [bones,4,4]
        with open(x.mesh_files[mid]) as f:
            lines = f.read().split("\n")
        vi = [k for k, l in enumerate(lines) if l.startswith("v ")]
        ni = [k for k, l in enumerate(lines) if l.startswith("vn ")]
        if len(vi) != len(bi):
            n["skin_baked"], n["skin_note"] = False, "vertex count differs from skin data"
            continue
        V = np.array([[float(t) for t in lines[k].split()[1:4]] for k in vi])
        V[:, 0] *= -1                                             # OBJ is right-handed
        Mv = np.einsum("vk,vkab->vab", bw, B[np.clip(bi, 0, len(B) - 1)])  # per-vertex blend
        Vh = np.concatenate([V, np.ones((len(V), 1))], axis=1)
        Vp = np.einsum("vab,vb->va", Mv, Vh)[:, :3]
        for k, row in zip(vi, Vp):
            lines[k] = "v {:.9G} {:.9G} {:.9G}".format(-row[0], row[1], row[2])
        if len(ni) == len(vi):
            Nn = np.array([[float(t) for t in lines[k].split()[1:4]] for k in ni])
            Nn[:, 0] *= -1
            Nr = np.einsum("vab,vb->va", Mv[:, :3, :3], Nn)
            Nr /= np.maximum(np.linalg.norm(Nr, axis=1, keepdims=True), 1e-12)
            for k, row in zip(ni, Nr):
                lines[k] = "vn {:.9G} {:.9G} {:.9G}".format(-row[0], row[1], row[2])
        out[mid] = "\n".join(lines)
        n["skin_baked"] = True
    return out


def _copy_meshes(x, mesh_ids, dest, mtl_file, mat_name, mesh_mat=None, baked=None):
    """`mesh_mat` maps mesh id -> the slot-ordered material names of the node that
    carries it, so each sub-mesh group gets its own `usemtl`. `baked` maps mesh id
    -> OBJ text already posed by its skeleton (see bake_skinned_nodes)."""
    mesh_mat, baked = mesh_mat or {}, baked or {}
    out = []
    for m in mesh_ids:
        src = x.mesh_files.get(m)
        if not src or not os.path.exists(src):
            continue
        dst = os.path.join(dest, os.path.basename(src))
        use = mesh_mat.get(m) or ([mat_name] if mat_name else None)
        if m in baked:
            body = baked[m]
            if mtl_file and use:
                body = attach_material_to_obj(body, mtl_file, use)
            with open(dst, "w") as f:
                f.write(body)
        elif mtl_file and use:
            with open(src) as f:
                body = f.read()
            body = attach_material_to_obj(body, mtl_file, use)
            groups, usemtl = obj_material_check(body)
            if usemtl < groups:
                x.errors["obj:unpainted-submesh"] += groups - usemtl
            with open(dst, "w") as f:
                f.write(body)
        elif not os.path.exists(dst):
            _link_or_copy(src, dst)
        out.append(os.path.basename(dst))
    return out


def _copy_animations(x, agg, dest):
    ctrl = (agg.get("animator") or {}).get("controller")
    if not ctrl:
        return []
    src_dir = os.path.join(x.out, "animations")
    out, ad = [], os.path.join(dest, "animations")
    cpath = os.path.join(src_dir, "controllers", safe_name(ctrl) + ".json")
    if os.path.exists(cpath):
        os.makedirs(ad, exist_ok=True)
        dst = os.path.join(ad, os.path.basename(cpath))
        if not os.path.exists(dst):
            _link_or_copy(cpath, dst)
        out.append(os.path.basename(dst))
        try:
            with open(cpath) as f:
                for clip in (json.load(f).get("clips") or []):
                    if not clip:
                        continue
                    cl = os.path.join(src_dir, "clips", safe_name(clip) + ".json")
                    if os.path.exists(cl):
                        d2 = os.path.join(ad, os.path.basename(cl))
                        if not os.path.exists(d2):
                            _link_or_copy(cl, d2)
                        out.append(os.path.basename(d2))
        except Exception:
            pass
    return out


def _copy_particles(x, agg, dest):
    out = []
    for p in agg.get("particles", []):
        src = os.path.join(x.out, "particles", p)
        if not os.path.exists(src):
            continue
        pd = os.path.join(dest, "particles")
        os.makedirs(pd, exist_ok=True)
        dst = os.path.join(pd, p)
        if not os.path.exists(dst):
            _link_or_copy(src, dst)
        out.append(p)
    return out


def _geometry_status(agg):
    """Distinguish 'nothing extracted' from the two legitimate reasons for it."""
    if agg["meshes"] or agg["broken_pieces"]:
        return "extracted"
    if agg["external_meshes"]:
        kinds = [k for k in agg["external_meshes"] if k.startswith("builtin:")]
        if kinds:
            return "builtin-primitive"
        return "external-reference"
    renderers = set(agg.get("renderers") or [])
    if agg["particles"] or agg.get("particle_owners"):
        if not renderers - {"ParticleSystemRenderer", "TrailRenderer", "LineRenderer"}:
            return "particle-effect"
    if agg["sprites"]:
        return "sprite-based"
    if any(re.search(r"tube|rope|generator|verlet|procedural", s, re.I)
           for s in agg["scripts"]):
        return "procedural"
    if agg["materials"]:
        return "material-only (geometry on a child outside the walked depth, or runtime-built)"
    return "empty"


def _entity_readme(info):
    n = info["entity"]
    lines = [f"# {n}", ""]
    status = info["geometry_status"]
    bits = []
    if info["whole_mesh_files"]:
        bits.append(f"{len(info['whole_mesh_files'])} mesh")
    if info["broken_piece_files"]:
        bits.append(f"{len(info['broken_piece_files'])} fracture piece")
    if info["texture_slots"]:
        bits.append(f"{len(info['texture_slots'])} texture")
    if info["colliders"]:
        bits.append(f"{len(info['colliders'])} collider")
    if info["joints"]:
        bits.append(f"{len(info['joints'])} joint")
    if info["particles"]:
        bits.append(f"{len(info['particles'])} particle system")
    lines.append(f"Geometry: **{status}**. Contains: " + (", ".join(bits) or "no geometry") + ".")
    if info["levels_used"]:
        lines.append(f"Used {info['levels_used']} times across the level database"
                     + (f", first at level {info['first_level']}." if info["first_level"] else "."))
    lines.append("")
    if info["broken_piece_files"]:
        lines += ["Fracture pieces ship as **pre-modelled meshes** under `broken/` — the "
                  "original swaps them in on impact rather than fracturing at runtime. "
                  "Reproduce that approach; it is far cheaper on mobile.", ""]
    if status == "builtin-primitive":
        lines += ["Its mesh references `Library/unity default resources`, i.e. a Unity "
                  "**built-in primitive** (Sphere/Cube/Quad). Nothing is missing — "
                  "recreate with a primitive plus the material values below.", ""]
    if status == "particle-effect":
        lines += ["A VFX prefab: no mesh by design. Its full particle-module settings are "
                  "under `particles/` — every module value is recorded, so it can be "
                  "rebuilt exactly.", ""]
    if status == "procedural":
        lines += ["No static mesh: the geometry is **generated at runtime** by the scripts "
                  "listed in `entity.json`. Reimplement the generator, do not hunt for a model.", ""]
    if info["rigidbody"]:
        rb = info["rigidbody"]
        lines += [f"Rigidbody: mass `{rb.get('mass')}`, drag `{rb.get('drag')}`, "
                  f"angularDrag `{rb.get('angularDrag')}`, gravity `{rb.get('useGravity')}`.", ""]
    if info["materials"]:
        lines += ["Materials (full float/colour/keyword values in `entity.json`): "
                  + ", ".join(f"`{m}`" for m in info["materials"]), ""]
    if info["scripts"]:
        lines += ["Scripts on this object (names only — MonoBehaviour field values are "
                  "stripped in an IL2CPP build): "
                  + ", ".join(f"`{s}`" for s in info["scripts"][:20]), ""]
    nodes = info.get("nodes") or []
    if nodes:
        meshed = [n for n in nodes if n.get("mesh_file")]
        frac = [n for n in nodes if n.get("fracture")]
        lines += ["", f"**Node tree: {len(nodes)} nodes**, {len(meshed)} of them carrying a mesh"
                  + (f", {len(frac)} fracture debris" if frac else "") + ".",
                  "",
                  "`entity.json` → `nodes` is the rebuild recipe: each entry has `parent`, "
                  "`localPosition/Rotation/Scale`, `mesh_file`, `materials` (**slot order**), "
                  "`active` and `fracture`. Build the hierarchy from it — the flat "
                  "`whole_mesh_files` list cannot tell the body from the debris.", ""]
        top = [n for n in nodes if n.get("depth") == 1][:12]
        if top:
            lines += ["Direct children: " + ", ".join(f"`{n['name']}`" for n in top), ""]
    lines += ["Files: `entity.json` is the machine-readable rebuild recipe; "
              "`unity-import/ImportExtracted.cs` consumes it.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level docs
# ---------------------------------------------------------------------------

def write_import_md(x, out, formats, entities, fonts, level_analysis):
    lossy = [k for k, v in (formats or {}).items() if not v.get("lossless")]
    lossless = len(formats or {}) - len(lossy)
    builtin = [e["entity"] for e in entities if e["geometry_status"] == "builtin-primitive"]
    procedural = [e["entity"] for e in entities if e["geometry_status"] == "procedural"]
    skinned = [e["entity"] for e in entities
               if "SkinnedMeshRenderer" in (e.get("renderers") or [])]
    lines = [
        "# How to import this extraction", "",
        "Everything here came out of the shipped package. Treat it as **reference "
        "material**: the transferable output is the structure (schema, physics "
        "constants, entity taxonomy, architecture), not the copyrighted art.", "",
        "## What is directly usable", "",
        "| Asset | State |", "|---|---|",
        f"| Prefab node tree (`entity.json` → `nodes`) | **the object's real hierarchy**: "
        "per node its parent, local position/rotation/scale, the mesh file it carries, its "
        "materials **in slot order**, whether it is active, and whether it is fracture debris. "
        "Rebuild from this, not from the flat mesh list — a folder of OBJs cannot say which "
        "one is the body, which is a plank and which is debris. |\n"
        f"| Meshes (`.obj` + `.mtl`) | geometry intact; the node tree carries the Transform — "
        "check `entity.json.transform.localScale`, some models are authored in centimetres |",
        f"| Textures | **{lossless} lossless** (RGBA32/RGB24/Alpha8) · "
        f"**{len(lossy)} decoded from compressed** (ASTC/ETC/DXT) — re-compressing those "
        "costs a second generation of loss |",
        "| Sprites | cropped PNG; **apply `sprites/sprite-meta.json`** for pivot, "
        "pixels-per-unit and 9-slice borders or UI frames will stretch |",
        "| Audio | valid PCM WAV, import as-is |",
        f"| Fonts | {sum(1 for f in (fonts or {}).values() if f.get('file'))} real TTF/OTF "
        "files; regenerate TMP SDF assets from them |",
        "| Levels | plain JSON, engine-agnostic |",
        "| Physics | `physics.json` + `project-settings/` carry the original constants |",
        "| Materials | every float/colour/keyword in `materials.json` |",
        "| Shaders | interface only (`shaders/`) — see that folder's README for "
        "buy-vs-re-author |",
        "| Particles | every module in `particles/` |",
        "| Animations | clips + controllers in `animations/`; check `curves_status` per clip |",
        "", "## Importer flags you must set by hand", "",
        "- **sRGB vs linear** — Unity's texture importer defaults to sRGB; normal/mask/"
        "matcap maps must be switched to linear.",
        "- **Normal maps** — set the texture type; the tangent channel is not encoded in PNG.",
        "- **9-slice borders** — from `sprites/sprite-meta.json` (`border_LBRT`).",
        "- **Pixels-per-unit** — from the same file; it is not always 100.",
        "- **Mesh tangents** — recompute on import; OBJ carries none.", "",
        "## Known losses", "",
        "- **MonoBehaviour / ScriptableObject field values** are stripped in an IL2CPP "
        "release build. Balance tables, tuning configs and per-component script settings "
        "are the one genuine gap. Class *names* are in `ARCHITECTURE.md`.",
        "- **Shader HLSL / bytecode** is compiled per platform. The interface is recovered.",
        "- **C# method bodies** are AOT-compiled into `libil2cpp.so`.",
        "- **Skinning / bone weights** are not carried by OBJ"
        + (f" — affects: {', '.join(skinned[:8])}" if skinned else "") + ".",
        "- **Vertex colours** are not carried by OBJ.", "",
    ]
    if builtin:
        lines += ["## Built-in primitives (nothing missing)", "",
                  "These reference `Library/unity default resources` — recreate with a "
                  "Unity primitive plus the material values in their `entity.json`: "
                  + ", ".join(f"`{b}`" for b in builtin), ""]
    if procedural:
        lines += ["## Runtime-generated geometry", "",
                  "No static mesh exists for these; the original builds them at runtime: "
                  + ", ".join(f"`{p}`" for p in procedural), ""]
    ab = (level_analysis or {}).get("ab_variants", {})
    if ab.get("duplicate_ids"):
        lines += ["## Level A/B ladders", "",
                  f"{ab['duplicate_ids']} level ids ship two differing payloads — the "
                  "original is running a live A/B test on level difficulty. Differing "
                  "fields: " + ", ".join(f"`{k}` ×{v}" for k, v in
                                         sorted(ab["differing_fields"].items(),
                                                key=lambda x: -x[1])), ""]
    lines += ["## Rebuilding prefabs", "",
              "`unity-import/ImportExtracted.cs` walks `entities/*/entity.json` and "
              "recreates each object as a prefab with its meshes, materials, colliders, "
              "rigidbody and joints applied. Drop it into `Assets/Editor/` and run "
              "**Tools → Clone App → Import Extracted Assets**.", ""]
    with open(os.path.join(out, "IMPORT.md"), "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Previews
# ---------------------------------------------------------------------------

def render_previews(out_dir, entities, verbose=True):
    """Per-entity preview + a labelled contact sheet. Requires numpy+Pillow."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "render_mesh_preview", os.path.join(here, "render-mesh-preview.py"))
        rmp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rmp)
    except Exception as e:
        return {"rendered": 0, "error": f"preview renderer unavailable: {e}"}
    cells, failed = [], 0
    for info in entities:
        d = os.path.join(out_dir, "entities", safe_name(info["entity"], "entity"))
        objs = [f for f in sorted(os.listdir(d)) if f.endswith(".obj")] \
            if os.path.isdir(d) else []
        if not objs:
            continue
        try:
            img = rmp.render(os.path.join(d, objs[0]), size=192)
        except Exception:
            failed += 1
            continue
        if img is None:
            continue
        img.save(os.path.join(d, "preview.png"))
        cells.append((info["entity"], img))
    if cells:
        try:
            rmp.contact_sheet(cells, os.path.join(out_dir, "_contactsheet_entities.png"))
        except Exception:
            pass
    for pool, name in (("sprites", "_contactsheet_sprites.png"),
                       ("textures", "_contactsheet_textures.png")):
        p = os.path.join(out_dir, pool)
        if os.path.isdir(p):
            try:
                rmp.contact_sheet_from_dir(p, os.path.join(out_dir, name))
            except Exception:
                pass
    if verbose:
        print(f"previews: {len(cells)} rendered, {failed} failed", flush=True)
    return {"rendered": len(cells), "failed": failed}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def copy_unity_importer(out):
    """Ship the Unity Editor importer alongside the extraction."""
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "templates", "ImportExtracted.cs")
    if not os.path.exists(src):
        return None
    d = os.path.join(out, "unity-import")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "ImportExtracted.cs")
    shutil.copy2(src, dst)
    for extra in ("ExtractedNode.cs", "VerifyImport.cs"):
        e = os.path.join(os.path.dirname(src), extra)
        if os.path.exists(e):
            shutil.copy2(e, os.path.join(d, extra))
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("# Unity importer\n\n"
                "1. Copy `ImportExtracted.cs` and `VerifyImport.cs` into `Assets/Editor/`, and\n"
                "   `ExtractedNode.cs` into any non-Editor folder (e.g. `Assets/Scripts/`) —\n"
                "   a component defined in an Editor folder cannot be added to a prefab.\n"
                "2. Run **Tools > Clone App > Import Extracted Assets**, or batch:\n"
                "   `Unity -batchmode -executeMethod ImportExtracted.ImportBatch -cloneSource <game-assets>`.\n"
                "3. Verify: `python3 <clone-app>/scripts/expected-import.py <game-assets> > expect.json`, then\n"
                "   `Unity -batchmode -executeMethod VerifyImport.Run -cloneSource <game-assets> -cloneExpect expect.json`.\n\n"
                "It copies meshes and textures in, rebuilds materials from the "
                "recorded float/colour/texture values, and saves one prefab per "
                "entity with its colliders, rigidbody and joints applied.\n\n"
                "Joint *connected bodies* live in other prefabs — wire those up in "
                "the scene. Script field values are in `../scripts/` (one JSONL per "
                "class, by object id); each prefab carries an `ExtractedEntityNote` "
                "listing the script names to reimplement.\n")
    return dst


def default_scratch_dir(out_dir):
    """Put unpack scratch in the workdir's raw/ layer when there is one.

    A standard workdir is <pkg>/{deliverables,extracted,raw}; extraction writes
    to <pkg>/extracted/game-assets, so scratch belongs at <pkg>/raw/unity-work.
    Outside that shape, fall back to a sibling of the output dir **named after
    that output dir** — a bare `unity-work` sibling is shared by every extraction
    writing next to it, and two packages then silently merge into one dump.
    """
    out_dir = os.path.abspath(out_dir)
    parent = os.path.dirname(out_dir)
    if os.path.basename(parent) == "extracted":
        return os.path.join(os.path.dirname(parent), "raw", "unity-work")
    return os.path.join(parent, os.path.basename(out_dir) + ".unity-work")


def guard_scratch(scratch, pkg_path):
    """Scratch is reused across runs to save an unpack. Reuse is only safe when
    it was filled from the SAME package — otherwise the merge step silently mixes
    two games. Stamp it, and wipe on mismatch."""
    stamp = os.path.join(scratch, ".source")
    try:
        sig = f"{os.path.abspath(pkg_path)}\n{os.path.getsize(pkg_path)}\n"
    except OSError:
        sig = os.path.abspath(pkg_path) + "\n"
    if os.path.isdir(scratch):
        old = ""
        if os.path.exists(stamp):
            try:
                old = open(stamp).read()
            except OSError:
                old = ""
        if old != sig:
            if old:
                print(f"       scratch was filled from a different package - wiping {scratch}")
            else:
                print(f"       scratch has no source stamp - wiping {scratch}")
            shutil.rmtree(scratch, ignore_errors=True)
    os.makedirs(scratch, exist_ok=True)
    with open(stamp, "w") as f:
        f.write(sig)
    return scratch


def count_package_entries(pkg_path):
    """`expected` for the coverage manifest: archive entries in the package."""
    if os.path.isdir(pkg_path):
        return sum(len(files) for _, _, files in os.walk(pkg_path))
    try:
        with zipfile.ZipFile(pkg_path) as z:
            total, inner = 0, []
            for n in z.namelist():
                total += 1
                if n.lower().endswith(".apk"):
                    inner.append(n)
            for n in inner:
                try:
                    import io
                    with zipfile.ZipFile(io.BytesIO(z.read(n))) as iz:
                        total += len(iz.namelist())
                except Exception:
                    continue
            return total
    except zipfile.BadZipFile:
        return 0


def _ensure_native_lib_path():
    """TypeTreeGeneratorAPI loads capstone by bare name; on macOS dlopen only finds
    the copy it ships when that folder is on DYLD_LIBRARY_PATH, which dyld reads at
    process start. Re-exec once with it set."""
    try:
        import importlib.util
        spec = importlib.util.find_spec("TypeTreeGeneratorAPI")
    except Exception:
        return
    if not spec or not spec.origin or os.environ.get("_CLONE_APP_NATIVE_PATH"):
        return
    key = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    lib_dir = os.path.dirname(spec.origin)
    cur = os.environ.get(key, "")
    env = dict(os.environ, _CLONE_APP_NATIVE_PATH="1")
    if lib_dir not in cur.split(os.pathsep):
        env[key] = lib_dir + (os.pathsep + cur if cur else "")
        os.execve(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:], env)


def main(argv=None):
    if argv is None:
        _ensure_native_lib_path()
    ap = argparse.ArgumentParser(
        description="Extract every Unity asset from an APK/XAPK, grouped and "
                    "ready to import.")
    ap.add_argument("package", help="path to .apk / .xapk / already-unpacked dir")
    ap.add_argument("--out", required=True, help="game-assets output dir")
    ap.add_argument("--work",
                    help="scratch dir for unpacking. Defaults to <workdir>/raw/unity-work "
                         "when --out sits under a standard workdir, else <out>/../unity-work")
    ap.add_argument("--engine", default="unity", help="engine label for the manifest")
    ap.add_argument("--no-previews", action="store_true", help="skip mesh rendering")
    ap.add_argument("--max-entities", type=int, default=2000,
                    help="cap on grouped entity folders (0 = no cap); any drop is "
                         "recorded in the manifest notes, never silent")
    ap.add_argument("--keep-work", action="store_true",
                    help="deprecated: scratch is always kept (nothing is deleted "
                         "automatically; use clean-workdir.sh)")
    ap.add_argument("--bundles", action="append", default=[],
                    help="extra folder of asset bundles (CDN download, device UnityCache) "
                         "to load into the same environment; repeatable")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    verbose = not args.quiet
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    work = guard_scratch(os.path.abspath(args.work or default_scratch_dir(out)),
                         args.package)
    os.makedirs(work, exist_ok=True)

    def log(m):
        if verbose:
            print(m, flush=True)

    try:
        import UnityPy  # noqa: F401
    except ImportError:
        print("ERROR: UnityPy is not importable. Create the extraction venv first:\n"
              "  bash setup-extraction-venv.sh\n"
              "then run this script with that venv's python.", file=sys.stderr)
        return 3

    log(f"[1/11] unpacking {args.package}")
    roots = unpack_package(args.package, work)
    data_dirs = find_data_dirs(roots)
    if not data_dirs:
        print("ERROR: no assets/bin/Data found — is this a Unity package?", file=sys.stderr)
        return 4
    log(f"       {len(roots)} package root(s), {len(data_dirs)} Unity Data dir(s)")

    merged = os.path.join(work, "merged")
    stats = merge_sources(data_dirs, merged)
    bundles = find_bundle_files(roots, args.bundles)
    stats["bundles_found"] = len(bundles)
    stats["bundles_linked"] = link_bundles(bundles, merged)
    log(f"[2/11] merged {stats['linked']} files + {stats['merged_split_groups']} split groups"
        f" + {stats['bundles_linked']} asset bundles")

    il2cpp = find_il2cpp(roots)
    x = Extractor(merged, out, verbose=verbose, il2cpp=il2cpp)
    stats["bundles_loaded"] = sum(1 for k in getattr(x.env, "files", {})
                                  if os.path.basename(str(k)).startswith("bundle"))
    log(f"[3/11] loaded {x.total_objects} objects; script type trees: "
        f"{'rebuilt from ' + os.path.basename(il2cpp[0]) if x.script_types else 'not available'}")

    log("[4/11] textures / sprites / meshes / audio / fonts / text")
    formats = x.export_textures()
    x.export_sprites()
    x.export_meshes()
    x.export_audio()
    fonts = x.export_fonts()
    levels = x.export_textassets()

    log("[5/11] materials + shaders")
    x.export_materials()
    x.export_shaders()

    log("[6/11] particles")
    particles = x.export_particles()

    log("[7/11] animations")
    x.export_animations()

    log("[8/11] scripts / scenes / UI / project settings / architecture")
    x.export_scripts()
    x.export_scenes()
    x.export_ui()
    x.export_project_settings()
    x.export_architecture()

    log("[9/11] levels + entity grouping")
    level_analysis = analyse_levels(levels)
    if levels:
        x.write_json("levels/level-analysis.json", level_analysis)
    else:
        x.notes.append("No level data found as TextAssets. Either this game stores "
                       "levels in ScriptableObjects (field values are stripped in an "
                       "IL2CPP build), builds them procedurally, or downloads them at "
                       "runtime — level-analysis.json is absent, not empty by accident.")
    wanted, ent_stats = collect_entity_names(levels, x, limit=args.max_entities)
    entities = EntityBuilder(x, wanted, level_analysis, particles).build()
    entities, dropped = prune_entities(entities, set(ent_stats.get("named_by_levels") or []))
    if dropped:
        x.notes.append(f"{len(dropped)} name-matched candidates were dropped as empty "
                       "UI objects (no geometry, colliders, joints, particles or sprites).")
    if ent_stats.get("dropped_for_limit"):
        x.notes.append(f"{ent_stats['dropped_for_limit']} further entity candidates were "
                       f"capped off by --max-entities; raise it to group them all.")
    index = write_entity_folders(x, entities, level_analysis, particles)
    x.export_physics(entity_names=set(entities))
    log(f"       {len(index)} entities "
        f"({ent_stats['prefab_roots']} prefab roots, "
        f"{ent_stats['matched_in_package']}/{ent_stats['from_levels']} level ids matched, "
        f"{ent_stats['hinted']} name-hinted)")

    if not args.no_previews:
        log("[10/11] previews")
        render_previews(out, index, verbose)
    else:
        log("[10/11] previews skipped")

    log("[11/11] manifest + docs")
    write_import_md(x, out, formats, index, fonts, level_analysis)
    copy_unity_importer(out)
    mechanics = []
    if level_analysis.get("levels"):
        mechanics.append({"name": "level database + mechanic introduction curve",
                          "confidence": "inferred"})
    if any(e["broken_piece_files"] for e in index):
        mechanics.append({"name": "pre-modelled fracture (not runtime fracture)",
                          "confidence": "inferred"})
    if x.counts.get("animation_clips"):
        mechanics.append({"name": "animation clips + controllers", "confidence": "inferred"})
    mb = getattr(x, "mb_stats", None) or {}
    mechanics.append({"name": "MonoBehaviour field values / balance tables",
                      "confidence": "decoded" if mb.get("values_complete") else "header-only"})
    notes = list(x.notes)
    for k, v in sorted(x.errors.items()):
        notes.append(f"{v} object(s) failed: {k}")
    notes.append("Shader HLSL and IL2CPP method bodies are not in the data files; script "
                 "field values are (scripts/), decoded from libil2cpp.so + global-metadata.dat.")
    manifest = build_manifest(args.engine, count_package_entries(args.package),
                              dict(x.counts), mechanics, notes,
                              extra={"entities": len(index),
                                     "unity_objects": x.total_objects,
                                     "unity_type_counts": dict(x.type_counts.most_common()),
                                     "monobehaviours": mb,
                                     "sources": stats,
                                     "errors": dict(x.errors),
                                     "level_analysis": {
                                         k: level_analysis.get(k)
                                         for k in ("levels", "distinct_entities",
                                                   "ab_variants")}})
    with open(os.path.join(out, "manifest.json"), "w") as f:
        _dump_json(manifest, f, indent=1, ensure_ascii=False, default=str)

    # Nothing is deleted automatically: later phases read back from the
    # unpacked tree, and removal is the user's call via clean-workdir.sh.

    log("\nEXTRACTED: " + ", ".join(f"{k}={v}" for k, v in sorted(x.counts.items())))
    if x.errors:
        log("ERRORS: " + ", ".join(f"{k}={v}" for k, v in sorted(x.errors.items())))
    log(f"manifest: {os.path.join(out, 'manifest.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
