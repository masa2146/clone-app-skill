// ImportExtracted.cs — rebuild prefabs from a clone-app Unity extraction.
//
// Drop this and VerifyImport.cs into Assets/Editor/, and ExtractedNode.cs into a
// non-Editor folder. Run Tools > Clone App > Import Extracted Assets, or batch:
//   Unity -batchmode -projectPath <p> -executeMethod ImportExtracted.ImportBatch \
//         -cloneSource <game-assets> [-cloneTarget Assets/Extracted] -quit
// It reads every entities/<Name>/entity.json and rebuilds the object as a prefab
// from its node tree: the real hierarchy and local transforms, each node's mesh
// (every OBJ group as one sub-mesh, in order), its materials slot by slot, and its
// own colliders, rigidbody and joints. Script field values are not applied — they
// are in game-assets/scripts/ (by object id) for when you reimplement a script.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

/// <summary>Import settings for extracted OBJs: no material import (materials are
/// rebuilt from the recorded values), no welding or reordering — the verifier
/// compares triangle counts and bounds against the source files.</summary>
public class ExtractedModelPostprocessor : AssetPostprocessor
{
    private void OnPreprocessModel()
    {
        if (!assetPath.EndsWith(".obj", StringComparison.OrdinalIgnoreCase) ||
            !assetPath.Replace("\\", "/").Contains("/Entities/")) return;
        var mi = (ModelImporter)assetImporter;
        mi.materialImportMode = ModelImporterMaterialImportMode.None;
        mi.importAnimation = false;
        mi.isReadable = true;
        mi.weldVertices = false;
        mi.optimizeMeshPolygons = false;
        mi.optimizeMeshVertices = false;
        mi.meshCompression = ModelImporterMeshCompression.Off;
        mi.globalScale = 1f;
    }
}

public class ImportExtracted : EditorWindow
{
    private string sourceDir = "";
    private string targetDir = "Assets/Extracted";
    private bool importTextures = true;
    private bool buildPrefabs = true;
    private Vector2 scroll;
    private readonly List<string> log = new List<string>();
    private int prefabsMade, prefabsFailed;

    [MenuItem("Tools/Clone App/Import Extracted Assets")]
    public static void Open()
    {
        GetWindow<ImportExtracted>("Import Extracted");
    }

    /// <summary>Batch entry: -cloneSource <game-assets> [-cloneTarget Assets/Extracted].
    /// Exits 1 when any prefab failed to build.</summary>
    public static void ImportBatch()
    {
        var w = CreateInstance<ImportExtracted>();
        w.sourceDir = Arg("-cloneSource", "");
        w.targetDir = Arg("-cloneTarget", "Assets/Extracted");
        w.Run();
        Console.WriteLine($"[ImportExtracted] prefabs made {w.prefabsMade}, failed {w.prefabsFailed}");
        EditorApplication.Exit(w.prefabsFailed > 0 || w.prefabsMade == 0 ? 1 : 0);
    }

    internal static string Arg(string key, string fallback)
    {
        var a = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(a, key);
        return i >= 0 && i + 1 < a.Length ? a[i + 1] : fallback;
    }

    private void OnGUI()
    {
        EditorGUILayout.LabelField("clone-app extraction importer", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(
            "Select the game-assets/ folder produced by unity-extract.py.\n" +
            "Extracted art is reference material — check your rights before shipping it.",
            MessageType.Info);

        using (new EditorGUILayout.HorizontalScope())
        {
            sourceDir = EditorGUILayout.TextField("game-assets dir", sourceDir);
            if (GUILayout.Button("Browse", GUILayout.Width(70)))
            {
                var p = EditorUtility.OpenFolderPanel("Select game-assets", "", "");
                if (!string.IsNullOrEmpty(p)) sourceDir = p;
            }
        }
        targetDir = EditorGUILayout.TextField("Import into", targetDir);
        importTextures = EditorGUILayout.Toggle("Copy textures", importTextures);
        buildPrefabs = EditorGUILayout.Toggle("Build prefabs", buildPrefabs);

        GUI.enabled = Directory.Exists(sourceDir);
        if (GUILayout.Button("Import", GUILayout.Height(30))) Run();
        GUI.enabled = true;

        scroll = EditorGUILayout.BeginScrollView(scroll);
        foreach (var line in log) EditorGUILayout.LabelField(line);
        EditorGUILayout.EndScrollView();
    }

    private void Log(string m)
    {
        log.Add(m);
        Debug.Log("[ImportExtracted] " + m);
    }

    private void Run()
    {
        log.Clear();
        prefabsMade = prefabsFailed = 0;
        var entitiesDir = Path.Combine(sourceDir, "entities");
        if (!Directory.Exists(entitiesDir))
        {
            Log("ERROR: no entities/ under " + sourceDir);
            return;
        }
        foreach (var sub in new[] { "Entities", "Materials", "Prefabs" })
            Directory.CreateDirectory(Path.Combine(targetDir, sub));

        var folders = Directory.GetDirectories(entitiesDir).OrderBy(f => f, StringComparer.Ordinal).ToArray();
        try
        {
            AssetDatabase.StartAssetEditing();
            foreach (var folder in folders)
                if (File.Exists(Path.Combine(folder, "entity.json"))) CopyEntityAssets(folder);
        }
        finally
        {
            AssetDatabase.StopAssetEditing();
            AssetDatabase.Refresh();
        }

        if (buildPrefabs)
        {
            foreach (var folder in folders)
            {
                if (!File.Exists(Path.Combine(folder, "entity.json"))) continue;
                try { BuildPrefab(folder); prefabsMade++; }
                catch (Exception e)
                {
                    prefabsFailed++;
                    Log("FAIL prefab " + Path.GetFileName(folder) + ": " + e);
                }
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
        }
        Log($"prefabs made {prefabsMade}, failed {prefabsFailed}. Prefabs in {targetDir}/Prefabs.");
    }

    // -- asset copy --------------------------------------------------------

    /// <summary>Each entity gets its own folder: OBJs of different entities share
    /// file names (every entity's .mtl is materials.mtl, and one mesh carries a
    /// different usemtl per entity), so one flat folder let the first copy win.</summary>
    private string EntityDir(string folder) =>
        Path.Combine(targetDir, "Entities", SafeName(Path.GetFileName(folder))).Replace("\\", "/");

    private void CopyEntityAssets(string folder)
    {
        var dest = EntityDir(folder);
        Directory.CreateDirectory(dest);
        foreach (var obj in Directory.GetFiles(folder, "*.obj")) CopyInto(obj, dest);
        var broken = Path.Combine(folder, "broken");
        if (Directory.Exists(broken))
            foreach (var obj in Directory.GetFiles(broken, "*.obj")) CopyInto(obj, dest);
        var spr = Path.Combine(folder, "sprites");
        if (Directory.Exists(spr))
        {
            Directory.CreateDirectory(Path.Combine(dest, "sprites"));
            foreach (var png in Directory.GetFiles(spr, "*.png")) CopyInto(png, Path.Combine(dest, "sprites"));
        }
        var tex = Path.Combine(folder, "textures");
        if (importTextures && Directory.Exists(tex))
        {
            Directory.CreateDirectory(Path.Combine(dest, "textures"));
            foreach (var png in Directory.GetFiles(tex, "*.png")) CopyInto(png, Path.Combine(dest, "textures"));
        }
    }

    private static void CopyInto(string src, string destDir)
    {
        var dest = Path.Combine(destDir, Path.GetFileName(src));
        if (!File.Exists(dest)) File.Copy(src, dest);
    }

    // -- prefab rebuild ----------------------------------------------------

    private void BuildPrefab(string folder)
    {
        var info = EntityInfo.Parse(File.ReadAllText(Path.Combine(folder, "entity.json")));
        if (info == null || string.IsNullOrEmpty(info.entity)) throw new Exception("unreadable entity.json");
        var dir = EntityDir(folder);
        var go = new GameObject(info.entity);
        try
        {
            if (info.nodes.Count > 0) BuildFromNodes(info, go, dir);
            else BuildFlat(info, go, dir);

            var note = go.AddComponent<ExtractedEntityNote>();
            if (note != null)
            {
                note.sourceEntity = info.entity;
                note.originalScripts = string.Join(", ", info.scripts);
                note.notes = "geometry_status=" + info.geometryStatus +
                             "; joint connected bodies need wiring in the scene; " +
                             "script field values: game-assets/scripts/ (by object id).";
            }
            var prefabPath = Path.Combine(targetDir, "Prefabs", SafeName(Path.GetFileName(folder)) + ".prefab")
                .Replace("\\", "/");
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath, out bool ok);
            if (!ok) throw new Exception("SaveAsPrefabAsset failed");
        }
        finally
        {
            DestroyImmediate(go);
        }
    }

    /// <summary>Rebuild the prefab's real hierarchy: one GameObject per extracted
    /// node under its REAL parent, with its local transform, mesh, slot-ordered
    /// materials, colliders, rigidbody and joints. Fracture debris keeps its place
    /// in the tree (re-parenting it moved every piece); the top debris node is
    /// simply inactive, which is the intact state.</summary>
    private void BuildFromNodes(EntityInfo info, GameObject root, string dir)
    {
        var made = new GameObject[info.nodes.Count];
        for (int i = 0; i < info.nodes.Count; i++)
        {
            var n = info.nodes[i];
            GameObject g;
            if (i == 0) g = root;
            else
            {
                g = new GameObject(string.IsNullOrEmpty(n.name) ? "node" : n.name);
                var parent = n.parent >= 0 && n.parent < i && made[n.parent] != null
                    ? made[n.parent].transform : root.transform;
                g.transform.SetParent(parent, false);
            }
            made[i] = g;

            if (n.localPosition != null) g.transform.localPosition = n.localPosition.Value;
            if (n.localRotation != null) g.transform.localRotation = n.localRotation.Value;
            if (n.localScale != null) g.transform.localScale = n.localScale.Value;
            bool debrisTop = n.fracture && (n.parent < 0 || !info.nodes[n.parent].fracture);
            if (i != 0 && (!n.active || debrisTop)) g.SetActive(false);

            var tag = g.AddComponent<ExtractedNode>();
            if (tag != null) { tag.nodeId = n.id; tag.nodeIndex = i; }

            if (!string.IsNullOrEmpty(n.meshFile))
            {
                var mesh = LoadObjMesh(dir + "/" + n.meshFile);
                if (mesh != null)
                {
                    g.AddComponent<MeshFilter>().sharedMesh = mesh;
                    var mr = g.AddComponent<MeshRenderer>();
                    var keys = n.mtlMaterials.Count > 0 ? n.mtlMaterials : n.materials;
                    mr.sharedMaterials = keys.Select(k => ResolveMaterial(info, k, dir)).ToArray();
                }
            }
            else if (!string.IsNullOrEmpty(n.builtinMesh) && BuiltinMesh(n.builtinMesh) is Mesh bm)
            {
                // a Unity primitive (the arena floor is a built-in Plane): same mesh, its own materials
                g.AddComponent<MeshFilter>().sharedMesh = bm;
                var keys = n.mtlMaterials.Count > 0 ? n.mtlMaterials : n.materials;
                g.AddComponent<MeshRenderer>().sharedMaterials = keys.Select(k => ResolveMaterial(info, k, dir)).ToArray();
            }
            if (!string.IsNullOrEmpty(n.spriteFile))
            {
                var sprite = LoadSprite(dir + "/sprites/" + n.spriteFile, n.spritePpu, n.spritePivot);
                if (sprite != null)
                {
                    var sr = g.AddComponent<SpriteRenderer>();
                    sr.sprite = sprite;
                    if (n.spriteColor != null) sr.color = n.spriteColor.Value;
                }
            }
            foreach (var c in n.colliders) AddCollider(g, c, dir);
            if (n.rigidbody != null) ApplyRigidbody(g, n.rigidbody);
            foreach (var j in n.joints) AddJoint(g, j);
        }
        // older entity.json without per-node physics: entity-level lists on the root
        if (!info.nodes.Any(x => x.colliders.Count > 0 || x.rigidbody != null))
        {
            foreach (var c in info.colliders) AddCollider(root, c, dir);
            if (info.rigidbody != null) ApplyRigidbody(root, info.rigidbody);
            foreach (var j in info.joints) AddJoint(root, j);
        }
    }

    private void BuildFlat(EntityInfo info, GameObject go, string dir)
    {
        foreach (var meshFile in info.wholeMeshFiles)
        {
            var mesh = LoadObjMesh(dir + "/" + meshFile);
            if (mesh == null) continue;
            var child = new GameObject(Path.GetFileNameWithoutExtension(meshFile));
            child.transform.SetParent(go.transform, false);
            child.AddComponent<MeshFilter>().sharedMesh = mesh;
            child.AddComponent<MeshRenderer>().sharedMaterial =
                ResolveMaterial(info, info.materials.Keys.FirstOrDefault(), dir);
        }
        foreach (var c in info.colliders) AddCollider(go, c, dir);
        if (info.rigidbody != null) ApplyRigidbody(go, info.rigidbody);
    }

    private static void AddCollider(GameObject go, ColliderInfo c, string dir)
    {
        switch (c.type)
        {
            case "BoxCollider":
                var bc = go.AddComponent<BoxCollider>();
                if (c.center != null) bc.center = c.center.Value;
                if (c.size != null) bc.size = c.size.Value;
                bc.isTrigger = c.isTrigger;
                break;
            case "SphereCollider":
                var sc = go.AddComponent<SphereCollider>();
                if (c.center != null) sc.center = c.center.Value;
                if (c.radius.HasValue) sc.radius = c.radius.Value;
                sc.isTrigger = c.isTrigger;
                break;
            case "CapsuleCollider":
                var cc = go.AddComponent<CapsuleCollider>();
                if (c.center != null) cc.center = c.center.Value;
                if (c.radius.HasValue) cc.radius = c.radius.Value;
                if (c.height.HasValue) cc.height = c.height.Value;
                if (c.direction.HasValue) cc.direction = c.direction.Value;
                cc.isTrigger = c.isTrigger;
                break;
            case "MeshCollider":
                var mc = go.AddComponent<MeshCollider>();
                mc.convex = c.convex;
                if (!string.IsNullOrEmpty(c.meshFile)) mc.sharedMesh = LoadObjMesh(dir + "/" + c.meshFile);
                else if (go.TryGetComponent<MeshFilter>(out var mf)) mc.sharedMesh = mf.sharedMesh;
                if (c.convex) mc.isTrigger = c.isTrigger;
                break;
        }
    }

    private static void ApplyRigidbody(GameObject go, RigidbodyInfo r)
    {
        var rb = go.AddComponent<Rigidbody>();
        if (r.mass.HasValue) rb.mass = r.mass.Value;
        if (r.drag.HasValue) rb.linearDamping = r.drag.Value;
        if (r.angularDrag.HasValue) rb.angularDamping = r.angularDrag.Value;
        rb.useGravity = r.useGravity;
        rb.isKinematic = r.isKinematic;
    }

    private static void AddJoint(GameObject go, JointInfo j)
    {
        // connected bodies live in other objects; wire them up in the scene
        if (j.type == "ConfigurableJoint") go.AddComponent<ConfigurableJoint>();
        else if (j.type == "HingeJoint") go.AddComponent<HingeJoint>();
        else if (j.type == "FixedJoint") go.AddComponent<FixedJoint>();
        else if (j.type == "SpringJoint") go.AddComponent<SpringJoint>();
    }

    /// <summary>Unity 6 imports every OBJ group as its own Mesh sub-asset, so
    /// LoadAssetAtPath returns only the first group — a multi-material object came
    /// in with one region. The exporter writes `g name` (vertices) then one
    /// `g name_N` per sub-mesh; rebuild ONE mesh whose sub-mesh N is group N, so
    /// material slot N lands on the region it was made for.</summary>
    internal static Mesh LoadObjMesh(string objPath)
    {
        var groups = AssetDatabase.LoadAllAssetsAtPath(objPath).OfType<Mesh>()
            .Where(m => m.vertexCount > 0 && m.subMeshCount > 0 && m.GetIndexCount(0) > 0)
            .OrderBy(m => GroupIndex(m.name)).ThenBy(m => m.name, StringComparer.Ordinal)
            .ToList();
        if (groups.Count == 0) return null;
        if (groups.Count == 1) return groups[0];
        var cachePath = Path.ChangeExtension(objPath, null) + ".submeshes.asset";
        var cached = AssetDatabase.LoadAssetAtPath<Mesh>(cachePath);
        if (cached != null) return cached;
        var merged = new Mesh
        {
            name = Path.GetFileNameWithoutExtension(objPath),
            indexFormat = UnityEngine.Rendering.IndexFormat.UInt32,
        };
        merged.CombineMeshes(groups.Select(m => new CombineInstance
            { mesh = m, transform = Matrix4x4.identity }).ToArray(), false, false);
        merged.RecalculateBounds();
        AssetDatabase.CreateAsset(merged, cachePath);
        return merged;
    }

    private static readonly Dictionary<string, Mesh> builtins = new Dictionary<string, Mesh>();

    /// <summary>Unity's own primitive mesh asset by name (Cube, Plane, Quad, ...).</summary>
    internal static Mesh BuiltinMesh(string name)
    {
        if (builtins.TryGetValue(name, out var m)) return m;
        if (!Enum.TryParse(name, out PrimitiveType t)) return null;
        var tmp = GameObject.CreatePrimitive(t);
        m = tmp.GetComponent<MeshFilter>().sharedMesh;
        DestroyImmediate(tmp);
        return builtins[name] = m;
    }

    /// <summary>Import a sprite PNG with the original pixels-per-unit and pivot.</summary>
    private static Sprite LoadSprite(string path, float? ppu, Vector2? pivot)
    {
        if (AssetImporter.GetAtPath(path) is TextureImporter ti)
        {
            var settings = new TextureImporterSettings();
            ti.ReadTextureSettings(settings);
            bool dirty = ti.textureType != TextureImporterType.Sprite || settings.spriteMode != (int)SpriteImportMode.Single;
            // SetTextureSettings writes textureType too: set it on the settings, not the importer
            settings.textureType = TextureImporterType.Sprite;
            settings.spriteMode = (int)SpriteImportMode.Single;
            if (ppu.HasValue && Mathf.Abs(settings.spritePixelsPerUnit - ppu.Value) > 1e-3f)
            { settings.spritePixelsPerUnit = ppu.Value; dirty = true; }
            if (pivot.HasValue && (settings.spritePivot - pivot.Value).sqrMagnitude > 1e-8f)
            { settings.spriteAlignment = (int)SpriteAlignment.Custom; settings.spritePivot = pivot.Value; dirty = true; }
            if (dirty) { ti.SetTextureSettings(settings); ti.SaveAndReimport(); }
        }
        return AssetDatabase.LoadAssetAtPath<Sprite>(path);
    }

    /// <summary>`name_12` -> 12 (numeric, so _10 sorts after _9); no suffix -> -1.</summary>
    private static int GroupIndex(string meshName)
    {
        int us = meshName.LastIndexOf('_');
        return us >= 0 && int.TryParse(meshName.Substring(us + 1), out var k) ? k : -1;
    }

    /// <summary>One Unity material per extracted material ID (two materials may
    /// share a name; a name-keyed asset let the first one win for every entity),
    /// with its own textures, colours and floats.</summary>
    private Material ResolveMaterial(EntityInfo info, string key, string dir)
    {
        if (string.IsNullOrEmpty(key) || !info.materials.TryGetValue(key, out var mi)) return null;
        var path = (targetDir + "/Materials/" + MaterialAssetName(mi.id ?? key) + ".mat");
        var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (existing != null) return existing;

        var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
        var mat = new Material(shader) { name = mi.name ?? key };
        foreach (var kv in mi.textureFiles)
        {
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(dir + "/" + kv.Value.Replace("\\", "/"));
            if (tex == null) continue;
            var slot = mat.HasProperty(kv.Key) ? kv.Key
                : (kv.Key == "_MainTex" || kv.Key == "_BaseMap")
                    ? (mat.HasProperty("_BaseMap") ? "_BaseMap" : "_MainTex") : null;
            if (slot != null) mat.SetTexture(slot, tex);
        }
        // _BaseColor last: URP and toon shaders take the albedo from it, and a legacy
        // _Color written after it painted a gold lock grey
        foreach (var kv in mi.colors.OrderBy(c => c.Key == "_BaseColor" ? 1 : 0))
        {
            var slot = mat.HasProperty(kv.Key) ? kv.Key
                : kv.Key == "_BaseColor" && mat.HasProperty("_Color") ? "_Color"
                : kv.Key == "_Color" && mat.HasProperty("_BaseColor") ? "_BaseColor" : null;
            if (slot != null) mat.SetColor(slot, kv.Value);
        }
        foreach (var kv in mi.floats) if (mat.HasProperty(kv.Key)) mat.SetFloat(kv.Key, kv.Value);
        AssetDatabase.CreateAsset(mat, path);
        return mat;
    }

    /// <summary>Material asset file name for an extracted id (`file:pathid`).</summary>
    internal static string MaterialAssetName(string id) => SafeName(id.Replace(":", "__"));

    internal static string SafeName(string s)
    {
        foreach (var c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_');
        return s.Replace(":", "_");
    }

    // -- entity.json model ---------------------------------------------------

    private class ColliderInfo
    {
        public string type, mesh, meshFile;
        public bool isTrigger, convex;
        public Vector3? center, size;
        public float? radius, height;
        public int? direction;
    }

    private class JointInfo { public string type, connectedBody; }

    private class RigidbodyInfo
    {
        public float? mass, drag, angularDrag;
        public bool useGravity, isKinematic;
    }

    private class NodeInfo
    {
        public string id, name, meshFile, builtinMesh, spriteFile;
        public float? spritePpu;
        public Vector2? spritePivot;
        public Color? spriteColor;
        public int parent = -1;
        public bool active = true, fracture;
        public Vector3? localPosition, localScale;
        public Quaternion? localRotation;
        public List<string> materials = new List<string>();
        // unique per entity; keys of entity.json "materials"
        public List<string> mtlMaterials = new List<string>();
        public List<ColliderInfo> colliders = new List<ColliderInfo>();
        public List<JointInfo> joints = new List<JointInfo>();
        public RigidbodyInfo rigidbody;
    }

    private class MaterialInfo
    {
        public string id, name;
        public Dictionary<string, string> textureFiles = new Dictionary<string, string>();
        public Dictionary<string, Color> colors = new Dictionary<string, Color>();
        public Dictionary<string, float> floats = new Dictionary<string, float>();
    }

    private class EntityInfo
    {
        public string entity, geometryStatus;
        public List<string> wholeMeshFiles = new List<string>();
        public List<string> scripts = new List<string>();
        public List<ColliderInfo> colliders = new List<ColliderInfo>();
        public List<JointInfo> joints = new List<JointInfo>();
        public RigidbodyInfo rigidbody;
        public List<NodeInfo> nodes = new List<NodeInfo>();
        public Dictionary<string, MaterialInfo> materials = new Dictionary<string, MaterialInfo>();

        private static ColliderInfo Collider(Dictionary<string, object> cd) => new ColliderInfo
        {
            type = MiniJson.Str(cd, "type"),
            mesh = MiniJson.Str(cd, "mesh"),
            meshFile = MiniJson.Str(cd, "mesh_file"),
            isTrigger = MiniJson.Bool(cd, "isTrigger"),
            convex = MiniJson.Bool(cd, "convex"),
            center = MiniJson.Vec(cd, "center"),
            size = MiniJson.Vec(cd, "size"),
            radius = MiniJson.Flt(cd, "radius"),
            height = MiniJson.Flt(cd, "height"),
            direction = MiniJson.Flt(cd, "direction") is float f ? (int?)Mathf.RoundToInt(f) : null,
        };

        private static RigidbodyInfo Body(Dictionary<string, object> rb) => new RigidbodyInfo
        {
            mass = MiniJson.Flt(rb, "mass"),
            drag = MiniJson.Flt(rb, "drag"),
            angularDrag = MiniJson.Flt(rb, "angularDrag"),
            useGravity = MiniJson.Bool(rb, "useGravity"),
            isKinematic = MiniJson.Bool(rb, "isKinematic"),
        };

        private static JointInfo Joint(Dictionary<string, object> jd) => new JointInfo
            { type = MiniJson.Str(jd, "type"), connectedBody = MiniJson.Str(jd, "connectedBody") };

        public static EntityInfo Parse(string json)
        {
            var node = MiniJson.Parse(json) as Dictionary<string, object>;
            if (node == null) return null;
            var e = new EntityInfo
            {
                entity = MiniJson.Str(node, "entity"),
                geometryStatus = MiniJson.Str(node, "geometry_status"),
            };
            foreach (var m in MiniJson.Arr(node, "whole_mesh_files")) e.wholeMeshFiles.Add(Convert.ToString(m));
            foreach (var s in MiniJson.Arr(node, "scripts")) e.scripts.Add(Convert.ToString(s));
            if (node.TryGetValue("rigidbody", out var rbo) && rbo is Dictionary<string, object> rb) e.rigidbody = Body(rb);
            foreach (var c in MiniJson.Arr(node, "colliders"))
                if (c is Dictionary<string, object> cd) e.colliders.Add(Collider(cd));
            foreach (var j in MiniJson.Arr(node, "joints"))
                if (j is Dictionary<string, object> jd) e.joints.Add(Joint(jd));
            if (node.TryGetValue("materials", out var mo) && mo is Dictionary<string, object> mats)
                foreach (var kv in mats)
                {
                    if (!(kv.Value is Dictionary<string, object> md)) continue;
                    var mi = new MaterialInfo { id = MiniJson.Str(md, "id"), name = MiniJson.Str(md, "name") };
                    if (md.TryGetValue("texture_files", out var tf) && tf is Dictionary<string, object> tfs)
                        foreach (var t in tfs) mi.textureFiles[t.Key] = Convert.ToString(t.Value);
                    if (md.TryGetValue("colors", out var mcs) && mcs is Dictionary<string, object> cls)
                        foreach (var c in cls)
                        {
                            var v = MiniJson.Floats(c.Value);
                            if (v.Count >= 4) mi.colors[c.Key] = new Color(v[0], v[1], v[2], v[3]);
                        }
                    if (md.TryGetValue("floats", out var mfs) && mfs is Dictionary<string, object> fss)
                        foreach (var f in fss) { try { mi.floats[f.Key] = Convert.ToSingle(f.Value); } catch { } }
                    e.materials[kv.Key] = mi;
                }
            foreach (var nd in MiniJson.Arr(node, "nodes"))
            {
                if (!(nd is Dictionary<string, object> n)) continue;
                var ni = new NodeInfo
                {
                    id = MiniJson.Str(n, "id"),
                    name = MiniJson.Str(n, "name"),
                    meshFile = MiniJson.Str(n, "mesh_file"),
                    builtinMesh = MiniJson.Str(n, "builtin_mesh"),
                    spriteFile = MiniJson.Str(n, "sprite_file"),
                    spritePpu = MiniJson.Flt(n, "sprite_ppu"),
                    parent = n.TryGetValue("parent", out var pv) && pv != null ? Convert.ToInt32(pv) : -1,
                    active = !n.TryGetValue("active", out var av) || Convert.ToBoolean(av),
                    fracture = n.TryGetValue("fracture", out var fv) && Convert.ToBoolean(fv),
                    localPosition = MiniJson.Vec(n, "localPosition"),
                    localScale = MiniJson.Vec(n, "localScale"),
                };
                var q = MiniJson.Floats(n.TryGetValue("localRotation", out var rv) ? rv : null);
                if (q.Count >= 4) ni.localRotation = new Quaternion(q[0], q[1], q[2], q[3]);
                var sp = MiniJson.Floats(n.TryGetValue("sprite_pivot", out var spv) ? spv : null);
                if (sp.Count >= 2) ni.spritePivot = new Vector2(sp[0], sp[1]);
                var sc = MiniJson.Floats(n.TryGetValue("sprite_color", out var scv) ? scv : null);
                if (sc.Count >= 4) ni.spriteColor = new Color(sc[0], sc[1], sc[2], sc[3]);
                foreach (var m in MiniJson.Arr(n, "materials")) ni.materials.Add(Convert.ToString(m));
                foreach (var m in MiniJson.Arr(n, "materials_mtl")) ni.mtlMaterials.Add(Convert.ToString(m));
                foreach (var c in MiniJson.Arr(n, "colliders"))
                    if (c is Dictionary<string, object> cd) ni.colliders.Add(Collider(cd));
                foreach (var j in MiniJson.Arr(n, "joints"))
                    if (j is Dictionary<string, object> jd) ni.joints.Add(Joint(jd));
                if (n.TryGetValue("rigidbody", out var nrb) && nrb is Dictionary<string, object> nrbd) ni.rigidbody = Body(nrbd);
                e.nodes.Add(ni);
            }
            return e;
        }
    }
}

// Tiny JSON parser — Unity's JsonUtility cannot read the nested, dynamic
// shape of entity.json, and pulling in a package for one importer is silly.
internal static class MiniJson
    {
        public static object Parse(string s)
        {
            int i = 0;
            return ParseValue(s, ref i);
        }

        public static string Str(Dictionary<string, object> d, string k)
            => d != null && d.TryGetValue(k, out var v) && v != null ? Convert.ToString(v) : null;

        public static bool Bool(Dictionary<string, object> d, string k)
            => d != null && d.TryGetValue(k, out var v) && v is bool b && b;

        public static float? Flt(Dictionary<string, object> d, string k)
        {
            if (d == null || !d.TryGetValue(k, out var v) || v == null) return null;
            try { return Convert.ToSingle(v); } catch { return null; }
        }

        public static List<object> Arr(Dictionary<string, object> d, string k)
            => d != null && d.TryGetValue(k, out var v) && v is List<object> l ? l : new List<object>();

        public static List<float> Floats(object v)
        {
            var outv = new List<float>();
            if (v is List<object> l)
                foreach (var x in l) { try { outv.Add(Convert.ToSingle(x)); } catch { } }
            return outv;
        }

        public static Vector3? Vec(Dictionary<string, object> d, string k)
        {
            if (d == null || !d.TryGetValue(k, out var v)) return null;
            var f = Floats(v);
            return f.Count >= 3 ? new Vector3(f[0], f[1], f[2]) : (Vector3?)null;
        }

        private static object ParseValue(string s, ref int i)
        {
            SkipWs(s, ref i);
            if (i >= s.Length) return null;
            switch (s[i])
            {
                case '{': return ParseObject(s, ref i);
                case '[': return ParseArray(s, ref i);
                case '"': return ParseString(s, ref i);
                case 't': i += 4; return true;
                case 'f': i += 5; return false;
                case 'n': i += 4; return null;
                case 'N': i += 3; return double.NaN;                 // NaN
                case 'I': i += 8; return double.PositiveInfinity;    // Infinity
                default:
                    if (s[i] == '-' && i + 1 < s.Length && s[i + 1] == 'I') { i += 9; return double.NegativeInfinity; }
                    int at = i;
                    var num = ParseNumber(s, ref i);
                    if (i == at) i++;      // never stall on a token we do not know
                    return num;
            }
        }

        private static Dictionary<string, object> ParseObject(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            i++; // {
            while (i < s.Length)
            {
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == '}') { i++; break; }
                var key = ParseString(s, ref i);
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ':') i++;
                d[key] = ParseValue(s, ref i);
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ',') i++;
            }
            return d;
        }

        private static List<object> ParseArray(string s, ref int i)
        {
            var l = new List<object>();
            i++; // [
            while (i < s.Length)
            {
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ']') { i++; break; }
                l.Add(ParseValue(s, ref i));
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ',') i++;
            }
            return l;
        }

        private static string ParseString(string s, ref int i)
        {
            SkipWs(s, ref i);
            if (i >= s.Length || s[i] != '"') return "";
            i++;
            var sb = new System.Text.StringBuilder();
            while (i < s.Length && s[i] != '"')
            {
                if (s[i] == '\\' && i + 1 < s.Length)
                {
                    i++;
                    switch (s[i])
                    {
                        case 'n': sb.Append('\n'); break;
                        case 't': sb.Append('\t'); break;
                        case 'r': sb.Append('\r'); break;
                        case 'u':
                            sb.Append((char)Convert.ToInt32(s.Substring(i + 1, 4), 16));
                            i += 4; break;
                        default: sb.Append(s[i]); break;
                    }
                }
                else sb.Append(s[i]);
                i++;
            }
            i++;
            return sb.ToString();
        }

        private static object ParseNumber(string s, ref int i)
        {
            int start = i;
            while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '-' || s[i] == '+' ||
                                    s[i] == '.' || s[i] == 'e' || s[i] == 'E')) i++;
            var t = s.Substring(start, i - start);
            if (double.TryParse(t, System.Globalization.NumberStyles.Float,
                                System.Globalization.CultureInfo.InvariantCulture, out var d))
                return d;
            return 0d;
        }

        private static void SkipWs(string s, ref int i)
        {
            while (i < s.Length && char.IsWhiteSpace(s[i])) i++;
        }
    }
#endif
