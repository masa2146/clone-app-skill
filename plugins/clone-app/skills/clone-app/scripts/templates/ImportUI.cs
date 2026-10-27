// ImportUI.cs — rebuild extracted uGUI canvases as prefabs, render them, verify them.
//
// Needs com.unity.ugui (TextMeshPro included) and ImportExtracted.cs + ExtractedNode.cs.
//   build : -executeMethod ImportUI.BuildBatch  -cloneSource <game-assets> -cloneCanvases A,B
//           [-cloneTexts texts-<locale>.json] [-cloneScreen 1080x2400] [-cloneTarget Assets/ExtractedUI]
//   render: -executeMethod ImportUI.RenderBatch -cloneUiPrefab <prefab> -cloneOut <png> [-cloneTransparent]
//   verify: -executeMethod ImportUI.VerifyBatch -cloneUiPrefab <prefab> -cloneExpect <expected-ui.json>
//           [-cloneReport <json>]   (expected-ui.py computes the boxes in Python)
//
// Every node gets the RectTransform the extraction recorded (anchors, pivot, position,
// size, scale, rotation), the Image's bound sprite with its pixels-per-unit, pivot and
// 9-slice border, the label's text (localized when a texts map is given), font, size,
// spacing, alignment and its material preset's outline/underlay. The canvas is sized
// in canvas units for the target screen through the recorded CanvasScaler, so a render
// is the same frame a phone of that size shows.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

public static class ImportUI
{
    private class Ctx
    {
        public string src, target;
        public Dictionary<string, Dictionary<string, object>> spriteMeta = new Dictionary<string, Dictionary<string, object>>();
        public Dictionary<string, string> textureFile = new Dictionary<string, string>();
        public Dictionary<string, string> fontFile = new Dictionary<string, string>();
        public Dictionary<string, Dictionary<string, object>> materials = new Dictionary<string, Dictionary<string, object>>();
        public Dictionary<string, string> texts = new Dictionary<string, string>();
        public Dictionary<string, TMP_FontAsset> fonts = new Dictionary<string, TMP_FontAsset>();
        public Dictionary<string, Material> fontMats = new Dictionary<string, Material>();
        public List<string> notes = new List<string>();
    }

    // -- build -------------------------------------------------------------

    public static void BuildBatch()
    {
        var c = new Ctx { src = ImportExtracted.Arg("-cloneSource", ""), target = ImportExtracted.Arg("-cloneTarget", "Assets/ExtractedUI") };
        var screen = ParseScreen(ImportExtracted.Arg("-cloneScreen", "1080x2400"));
        var names = ImportExtracted.Arg("-cloneCanvases", "").Split(',').Select(s => s.Trim()).Where(s => s.Length > 0).ToList();
        EnsureTmpEssentials();
        foreach (var sub in new[] { "Sprites", "Textures", "Fonts", "Materials", "Canvases" })
            Directory.CreateDirectory(Path.Combine(c.target, sub));
        LoadIndexes(c);
        var textsPath = ImportExtracted.Arg("-cloneTexts", "");
        if (File.Exists(textsPath) && MiniJson.Parse(File.ReadAllText(textsPath)) is Dictionary<string, object> tj &&
            tj.TryGetValue("texts", out var to) && to is Dictionary<string, object> tm)
            foreach (var kv in tm) c.texts[kv.Key] = Convert.ToString(kv.Value);

        var canvases = names.Select(n => (n, MiniJson.Parse(File.ReadAllText(Path.Combine(c.src, "ui", n + ".json")))
                                             as Dictionary<string, object>)).ToList();
        // copy every sprite / texture / font the canvases use, then import once
        var sprites = new HashSet<string>(); var textures = new HashSet<string>(); var fontNames = new HashSet<string>();
        foreach (var (_, cv) in canvases) Collect(cv["tree"] as Dictionary<string, object>, c, sprites, textures, fontNames);
        AssetDatabase.StartAssetEditing();
        try
        {
            foreach (var id in sprites) CopyAsset(c, "sprites", SpriteFile(c, id), "Sprites");
            foreach (var id in textures) if (c.textureFile.TryGetValue(id, out var tf)) CopyAsset(c, "textures", tf, "Textures");
            foreach (var f in fontNames) if (c.fontFile.TryGetValue(f, out var ff)) CopyAsset(c, "fonts", ff, "Fonts");
        }
        finally { AssetDatabase.StopAssetEditing(); AssetDatabase.Refresh(); }
        AssetDatabase.StartAssetEditing();
        try { foreach (var id in sprites) ConfigureSprite(c, id); }
        finally { AssetDatabase.StopAssetEditing(); AssetDatabase.Refresh(); }

        int made = 0;
        foreach (var (name, cv) in canvases)
        {
            var size = CanvasSize(cv.TryGetValue("scaler", out var so) ? so as Dictionary<string, object> : null, screen);
            var root = new GameObject(name, typeof(RectTransform), typeof(Canvas));
            root.GetComponent<Canvas>().renderMode = RenderMode.WorldSpace;
            var rt = (RectTransform)root.transform;
            rt.sizeDelta = size; rt.pivot = new Vector2(0.5f, 0.5f);
            var tag = root.AddComponent<ExtractedNode>();
            var tree = cv["tree"] as Dictionary<string, object>;
            tag.nodeId = MiniJson.Str(tree, "id");
            foreach (var ch in MiniJson.Arr(tree, "children"))
                BuildNode(ch as Dictionary<string, object>, root.transform, c);
            var path = $"{c.target}/Canvases/{ImportExtracted.SafeName(name)}.prefab";
            PrefabUtility.SaveAsPrefabAsset(root, path, out bool ok);
            UnityEngine.Object.DestroyImmediate(root);
            if (ok) made++; else c.notes.Add("prefab save failed: " + name);
        }
        AssetDatabase.SaveAssets();
        Console.WriteLine($"[ImportUI] canvases built {made}/{canvases.Count}" +
                          (c.notes.Count > 0 ? "; notes: " + string.Join(" | ", c.notes.Distinct().Take(30)) : ""));
        EditorApplication.Exit(made == canvases.Count ? 0 : 1);
    }

    private static void BuildNode(Dictionary<string, object> n, Transform parent, Ctx c)
    {
        if (n == null) return;
        var go = new GameObject(MiniJson.Str(n, "name") ?? "node", typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var rt = (RectTransform)go.transform;
        if (n.TryGetValue("rect", out var ro) && ro is Dictionary<string, object> r)
        {
            rt.anchorMin = V2(r, "anchorMin", new Vector2(0.5f, 0.5f));
            rt.anchorMax = V2(r, "anchorMax", new Vector2(0.5f, 0.5f));
            rt.pivot = V2(r, "pivot", new Vector2(0.5f, 0.5f));
            rt.sizeDelta = V2(r, "sizeDelta", Vector2.zero);
            rt.anchoredPosition = V2(r, "anchoredPosition", Vector2.zero);
            var s = MiniJson.Vec(r, "localScale");
            if (s != null) rt.localScale = s.Value;
            var q = MiniJson.Floats(r.TryGetValue("localRotation", out var qv) ? qv : null);
            if (q.Count >= 4) rt.localRotation = new Quaternion(q[0], q[1], q[2], q[3]);
        }
        else if (n.TryGetValue("transform", out var tro) && tro is Dictionary<string, object> tr)
        {
            // a plain Transform in the original: a point, placed from the parent's pivot
            rt.sizeDelta = Vector2.zero;
            var lp = MiniJson.Vec(tr, "localPosition");
            if (lp != null) rt.localPosition = lp.Value;
            var s = MiniJson.Vec(tr, "localScale");
            if (s != null) rt.localScale = s.Value;
            var q = MiniJson.Floats(tr.TryGetValue("localRotation", out var qv) ? qv : null);
            if (q.Count >= 4) rt.localRotation = new Quaternion(q[0], q[1], q[2], q[3]);
        }
        else rt.sizeDelta = Vector2.zero;
        var tag = go.AddComponent<ExtractedNode>();
        tag.nodeId = MiniJson.Str(n, "id");
        if (n.TryGetValue("active", out var av) && av is bool a && !a) go.SetActive(false);
        if (n.TryGetValue("canvas_group", out var cgo) && cgo is Dictionary<string, object> cg)
            go.AddComponent<CanvasGroup>().alpha = MiniJson.Flt(cg, "alpha") ?? 1f;

        var ui = n.TryGetValue("ui", out var uo) ? uo as Dictionary<string, object> : null;
        if (ui != null)
        {
            if (ui.TryGetValue("Image", out var io) && io is Dictionary<string, object> img) BuildImage(go, img, c);
            else if (ui.TryGetValue("RawImage", out var rio) && rio is Dictionary<string, object> raw) BuildRawImage(go, raw, c);
            else
            {
                var g = ui.FirstOrDefault(kv => kv.Key.StartsWith("Graphic:")).Value as Dictionary<string, object>;
                // a game's own Graphic subclass: draw the sprite it points at, as an Image
                var art = g != null && g.TryGetValue("art", out var ao) ? ao as Dictionary<string, object> : null;
                var spriteRef = art?.Values.OfType<Dictionary<string, object>>().FirstOrDefault(x => MiniJson.Str(x, "type") == "Sprite");
                if (spriteRef != null)
                    BuildImage(go, new Dictionary<string, object> { ["m_Sprite"] = spriteRef, ["m_Color"] = g.TryGetValue("m_Color", out var gc) ? gc : null }, c);
            }
            foreach (var key in new[] { "TextMeshProUGUI", "TextMeshPro" })
                if (ui.TryGetValue(key, out var to) && to is Dictionary<string, object> txt) { BuildText(go, n, txt, c); break; }
            if (ui.TryGetValue("Mask", out var mo) && mo is Dictionary<string, object> mask)
                go.AddComponent<Mask>().showMaskGraphic = MiniJson.Flt(mask, "m_ShowMaskGraphic") != 0;
            if (ui.ContainsKey("RectMask2D")) go.AddComponent<RectMask2D>();
            foreach (var fx in new[] { "Shadow", "Outline" })
                if (ui.TryGetValue(fx, out var fo) && fo is Dictionary<string, object> f && go.GetComponent<Graphic>() != null)
                {
                    var e = fx == "Outline" ? go.AddComponent<Outline>() : go.AddComponent<Shadow>();
                    e.effectColor = Col(f, "m_EffectColor", Color.black);
                    e.effectDistance = V2(f, "m_EffectDistance", new Vector2(1, -1));
                }
        }
        foreach (var ch in MiniJson.Arr(n, "children")) BuildNode(ch as Dictionary<string, object>, go.transform, c);
    }

    private static void BuildImage(GameObject go, Dictionary<string, object> img, Ctx c)
    {
        var im = go.AddComponent<Image>();
        var sref = img.TryGetValue("m_Sprite", out var so) ? so as Dictionary<string, object> : null;
        var sid = MiniJson.Str(sref, "ref");
        if (sid != null)
        {
            var file = SpriteFile(c, sid);
            im.sprite = file == null ? null : AssetDatabase.LoadAssetAtPath<Sprite>($"{c.target}/Sprites/{file}");
            if (im.sprite == null) c.notes.Add("sprite not imported: " + MiniJson.Str(sref, "name"));
        }
        im.color = Col(img, "m_Color", Color.white);
        im.type = (Image.Type)(int)(MiniJson.Flt(img, "m_Type") ?? 0);
        im.preserveAspect = MiniJson.Flt(img, "m_PreserveAspect") == 1;
        im.fillCenter = (MiniJson.Flt(img, "m_FillCenter") ?? 1) != 0;
        im.fillMethod = (Image.FillMethod)(int)(MiniJson.Flt(img, "m_FillMethod") ?? 4);
        im.fillAmount = MiniJson.Flt(img, "m_FillAmount") ?? 1f;
        im.fillOrigin = (int)(MiniJson.Flt(img, "m_FillOrigin") ?? 0);
        im.fillClockwise = (MiniJson.Flt(img, "m_FillClockwise") ?? 1) != 0;
        im.pixelsPerUnitMultiplier = MiniJson.Flt(img, "m_PixelsPerUnitMultiplier") ?? 1f;
        im.useSpriteMesh = MiniJson.Flt(img, "m_UseSpriteMesh") == 1;
        im.raycastTarget = false;
    }

    private static void BuildRawImage(GameObject go, Dictionary<string, object> raw, Ctx c)
    {
        var ri = go.AddComponent<RawImage>();
        var tid = MiniJson.Str(raw.TryGetValue("m_Texture", out var to) ? to as Dictionary<string, object> : null, "ref");
        if (tid != null && c.textureFile.TryGetValue(tid, out var file))
            ri.texture = AssetDatabase.LoadAssetAtPath<Texture2D>($"{c.target}/Textures/{file}");
        ri.color = Col(raw, "m_Color", Color.white);
        if (raw.TryGetValue("m_UVRect", out var uo) && uo is Dictionary<string, object> uv)
            ri.uvRect = new Rect(MiniJson.Flt(uv, "x") ?? 0, MiniJson.Flt(uv, "y") ?? 0,
                                 MiniJson.Flt(uv, "width") ?? 1, MiniJson.Flt(uv, "height") ?? 1);
        ri.raycastTarget = false;
    }

    private static void BuildText(GameObject go, Dictionary<string, object> n, Dictionary<string, object> t, Ctx c)
    {
        var tmp = go.AddComponent<TextMeshProUGUI>();
        var fontName = MiniJson.Str(t.TryGetValue("m_fontAsset", out var fo) ? fo as Dictionary<string, object> : null, "name");
        var fa = Font(c, fontName);
        if (fa != null) tmp.font = fa;
        // the localized string replaces the saved one: the game swaps it at runtime
        var textId = MiniJson.Arr(n, "scripts").OfType<Dictionary<string, object>>()
            .Where(s => MiniJson.Str(s, "class")?.StartsWith("TextMeshPro") == true)
            .Select(s => MiniJson.Str(s, "id")).FirstOrDefault();
        tmp.text = textId != null && c.texts.TryGetValue(textId, out var loc) ? loc : (MiniJson.Str(t, "m_text") ?? "");
        tmp.fontSize = MiniJson.Flt(t, "m_fontSize") ?? 36f;
        tmp.enableAutoSizing = MiniJson.Flt(t, "m_enableAutoSizing") == 1;
        tmp.fontSizeMin = MiniJson.Flt(t, "m_fontSizeMin") ?? 18f;
        tmp.fontSizeMax = MiniJson.Flt(t, "m_fontSizeMax") ?? 72f;
        tmp.color = Col(t, "m_fontColor", Color.white);
        tmp.characterSpacing = MiniJson.Flt(t, "m_characterSpacing") ?? 0f;
        tmp.wordSpacing = MiniJson.Flt(t, "m_wordSpacing") ?? 0f;
        tmp.lineSpacing = MiniJson.Flt(t, "m_lineSpacing") ?? 0f;
        var h = MiniJson.Flt(t, "m_HorizontalAlignment"); var v = MiniJson.Flt(t, "m_VerticalAlignment");
        if (h != null && v != null) tmp.alignment = (TextAlignmentOptions)((int)h.Value | (int)v.Value);
        else if (MiniJson.Flt(t, "m_textAlignment") is float al) tmp.alignment = (TextAlignmentOptions)(int)al;
        tmp.fontStyle = (FontStyles)(int)(MiniJson.Flt(t, "m_fontStyle") ?? 0);
        if (MiniJson.Flt(t, "m_TextWrappingMode") is float wm) tmp.textWrappingMode = (TextWrappingModes)(int)wm;
        else if (MiniJson.Flt(t, "m_enableWordWrapping") is float ew) tmp.textWrappingMode = ew != 0 ? TextWrappingModes.Normal : TextWrappingModes.NoWrap;
        if (MiniJson.Flt(t, "m_overflowMode") is float ov) tmp.overflowMode = (TextOverflowModes)(int)ov;
        if (t.TryGetValue("m_margin", out var mo) && mo is Dictionary<string, object> m)
            tmp.margin = new Vector4(MiniJson.Flt(m, "x") ?? 0, MiniJson.Flt(m, "y") ?? 0, MiniJson.Flt(m, "z") ?? 0, MiniJson.Flt(m, "w") ?? 0);
        tmp.raycastTarget = false;
        var matId = MiniJson.Str(t.TryGetValue("m_sharedMaterial", out var smo) ? smo as Dictionary<string, object> : null, "ref");
        if (fa != null && matId != null) tmp.fontSharedMaterial = FontMaterial(c, fa, matId);
    }

    /// <summary>The label's material preset (outline, underlay, dilate) applied to our font's material.</summary>
    private static Material FontMaterial(Ctx c, TMP_FontAsset fa, string matId)
    {
        var key = fa.name + "|" + matId;
        if (c.fontMats.TryGetValue(key, out var cached)) return cached;
        if (!c.materials.TryGetValue(matId, out var md)) return c.fontMats[key] = fa.material;
        var mat = new Material(fa.material) { name = (MiniJson.Str(md, "name") ?? matId) + " (rebuilt)" };
        if (md.TryGetValue("floats", out var fo) && fo is Dictionary<string, object> fl)
            foreach (var kv in fl)
                if (kv.Key != "_TextureWidth" && kv.Key != "_TextureHeight" && kv.Key != "_GradientScale" &&
                    !kv.Key.StartsWith("_Scale") && mat.HasProperty(kv.Key))
                    mat.SetFloat(kv.Key, Convert.ToSingle(kv.Value));
        if (md.TryGetValue("colors", out var co) && co is Dictionary<string, object> cl)
            foreach (var kv in cl)
            {
                var f = MiniJson.Floats(kv.Value);
                if (f.Count >= 4 && mat.HasProperty(kv.Key)) mat.SetColor(kv.Key, new Color(f[0], f[1], f[2], f[3]));
            }
        foreach (var kw in MiniJson.Arr(md, "keywords").Select(Convert.ToString)) mat.EnableKeyword(kw);
        AssetDatabase.CreateAsset(mat, $"{c.target}/Materials/{ImportExtracted.MaterialAssetName(matId)}__{ImportExtracted.SafeName(fa.name)}.mat");
        return c.fontMats[key] = mat;
    }

    /// <summary>A dynamic TMP font asset from the extracted TTF/OTF ("X SDF" -> font "X").
    /// The original font asset's glyph tables were never shipped as a font file.</summary>
    private static TMP_FontAsset Font(Ctx c, string assetName)
    {
        if (string.IsNullOrEmpty(assetName)) return null;
        if (c.fonts.TryGetValue(assetName, out var fa)) return fa;
        var family = assetName.Replace(" SDF", "").Trim();
        if (!c.fontFile.ContainsKey(family))
        {
            // a variant asset of a shipped font ("X_Closed SDF"): the longest family it starts with
            var baseName = c.fontFile.Keys.Where(k => family.StartsWith(k)).OrderByDescending(k => k.Length).FirstOrDefault();
            if (baseName != null) { c.notes.Add($"font {assetName} -> {baseName} (variant)"); family = baseName; }
        }
        if (!c.fontFile.TryGetValue(family, out var file)) { c.notes.Add("no font file for " + assetName); return c.fonts[assetName] = null; }
        var font = AssetDatabase.LoadAssetAtPath<UnityEngine.Font>($"{c.target}/Fonts/{file}");
        if (font == null) { c.notes.Add("font not imported: " + file); return c.fonts[assetName] = null; }
        var path = $"{c.target}/Fonts/{ImportExtracted.SafeName(family)} SDF.asset";
        fa = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(path);
        if (fa == null)
        {
            fa = TMP_FontAsset.CreateFontAsset(font, 90, 9, UnityEngine.TextCore.LowLevel.GlyphRenderMode.SDFAA,
                                               2048, 2048, AtlasPopulationMode.Dynamic, true);
            fa.name = family + " SDF";
            AssetDatabase.CreateAsset(fa, path);
            fa.material.name = fa.name + " Material";
            AssetDatabase.AddObjectToAsset(fa.material, fa);
            foreach (var tex in fa.atlasTextures) { tex.name = fa.name + " Atlas"; AssetDatabase.AddObjectToAsset(tex, fa); }
        }
        return c.fonts[assetName] = fa;
    }

    private static void Collect(Dictionary<string, object> n, Ctx c, HashSet<string> sprites, HashSet<string> textures, HashSet<string> fonts)
    {
        if (n == null) return;
        if (n.TryGetValue("ui", out var uo) && uo is Dictionary<string, object> ui)
            foreach (var kv in ui)
            {
                if (!(kv.Value is Dictionary<string, object> d)) continue;
                foreach (var v in d.Values.Concat(d.TryGetValue("art", out var ao) && ao is Dictionary<string, object> art ? art.Values : Enumerable.Empty<object>()))
                    if (v is Dictionary<string, object> refd && MiniJson.Str(refd, "ref") is string id)
                    {
                        var type = MiniJson.Str(refd, "type");
                        if (type == "Sprite") sprites.Add(id);
                        else if (type == "Texture2D") textures.Add(id);
                        else if (type == "MonoBehaviour" && kv.Key.StartsWith("TextMeshPro"))
                        {
                            var fam = (MiniJson.Str(refd, "name") ?? "").Replace(" SDF", "").Trim();
                            fonts.Add(c.fontFile.ContainsKey(fam) ? fam :
                                c.fontFile.Keys.Where(k => fam.StartsWith(k)).OrderByDescending(k => k.Length).FirstOrDefault() ?? fam);
                        }
                    }
            }
        foreach (var ch in MiniJson.Arr(n, "children")) Collect(ch as Dictionary<string, object>, c, sprites, textures, fonts);
    }

    private static void LoadIndexes(Ctx c)
    {
        if (MiniJson.Parse(File.ReadAllText(Path.Combine(c.src, "sprites", "sprite-meta.json"))) is Dictionary<string, object> sm)
            foreach (var kv in sm)
                if (kv.Value is Dictionary<string, object> m && MiniJson.Str(m, "id") is string id)
                { m["file"] = kv.Key; c.spriteMeta[id] = m; }
        var tf = Path.Combine(c.src, "textures", "texture-formats.json");
        if (File.Exists(tf) && MiniJson.Parse(File.ReadAllText(tf)) is Dictionary<string, object> tm)
            foreach (var kv in tm)
                if (kv.Value is Dictionary<string, object> m && MiniJson.Str(m, "id") is string id) c.textureFile[id] = kv.Key;
        var ff = Path.Combine(c.src, "fonts", "fonts.json");
        if (File.Exists(ff) && MiniJson.Parse(File.ReadAllText(ff)) is Dictionary<string, object> fm)
            foreach (var kv in fm)
                if (kv.Value is Dictionary<string, object> m && MiniJson.Str(m, "file") is string file) c.fontFile[kv.Key] = file;
        if (MiniJson.Parse(File.ReadAllText(Path.Combine(c.src, "materials.json"))) is Dictionary<string, object> mats)
            foreach (var kv in mats) if (kv.Value is Dictionary<string, object> m) c.materials[kv.Key] = m;
    }

    private static string SpriteFile(Ctx c, string id) =>
        c.spriteMeta.TryGetValue(id, out var m) ? MiniJson.Str(m, "file") : null;

    private static void CopyAsset(Ctx c, string srcDir, string file, string dstDir)
    {
        if (file == null) return;
        var from = Path.Combine(c.src, srcDir, file);
        var to = Path.Combine(c.target, dstDir, file);
        if (File.Exists(from) && !File.Exists(to)) File.Copy(from, to);
    }

    /// <summary>Import a sprite exactly as it shipped: pixels per unit, pivot, 9-slice border, no
    /// compression or mipmaps (a re-compressed UI plate is a second generation of artefacts).</summary>
    private static void ConfigureSprite(Ctx c, string id)
    {
        if (!c.spriteMeta.TryGetValue(id, out var m)) return;
        var path = $"{c.target}/Sprites/{MiniJson.Str(m, "file")}";
        if (!(AssetImporter.GetAtPath(path) is TextureImporter ti)) return;
        var s = new TextureImporterSettings();
        ti.ReadTextureSettings(s);
        s.textureType = TextureImporterType.Sprite;
        s.spriteMode = (int)SpriteImportMode.Single;
        s.spritePixelsPerUnit = MiniJson.Flt(m, "pixels_per_unit") is float ppu && ppu > 0 ? ppu : 100f;
        var pv = MiniJson.Floats(m.TryGetValue("pivot", out var pvo) ? pvo : null);
        if (pv.Count >= 2) { s.spriteAlignment = (int)SpriteAlignment.Custom; s.spritePivot = new Vector2(pv[0], pv[1]); }
        var b = MiniJson.Floats(m.TryGetValue("border_LBRT", out var bo) ? bo : null);
        if (b.Count >= 4) s.spriteBorder = new Vector4(b[0], b[1], b[2], b[3]);
        s.spriteMeshType = SpriteMeshType.FullRect;
        s.mipmapEnabled = false;
        s.alphaIsTransparency = true;
        ti.SetTextureSettings(s);
        ti.textureCompression = TextureImporterCompression.Uncompressed;
        ti.SaveAndReimport();
    }

    private static bool TmpReady() =>
        Shader.Find("TextMeshPro/Distance Field") != null && Resources.Load<TMP_Settings>("TMP Settings") != null;

    private static void EnsureTmpEssentials()
    {
        if (!TmpReady())
            throw new Exception("TextMeshPro essentials missing: run -executeMethod ImportUI.SetupBatch once first");
    }

    /// <summary>Import TMP Essential Resources (settings + SDF shaders) and exit when done.
    /// The import completes after the calling method returns, so it is its own step.</summary>
    public static void SetupBatch()
    {
        if (TmpReady()) { Console.WriteLine("[ImportUI] TMP essentials present"); EditorApplication.Exit(0); return; }
        var pkg = Path.GetFullPath("Packages/com.unity.ugui/Package Resources/TMP Essential Resources.unitypackage");
        if (!File.Exists(pkg)) { Console.WriteLine("[ImportUI] not found: " + pkg); EditorApplication.Exit(1); return; }
        AssetDatabase.importPackageCompleted += _ => { Console.WriteLine("[ImportUI] TMP essentials imported"); EditorApplication.Exit(0); };
        AssetDatabase.importPackageFailed += (_, err) => { Console.WriteLine("[ImportUI] TMP import failed: " + err); EditorApplication.Exit(1); };
        AssetDatabase.ImportPackage(pkg, false);
    }

    /// <summary>Canvas size in canvas units for a screen, through a CanvasScaler (as gen-ui-map.py).</summary>
    internal static Vector2 CanvasSize(Dictionary<string, object> scaler, Vector2 screen)
    {
        if (scaler == null) return screen;
        float k = 1f;
        if ((MiniJson.Flt(scaler, "m_UiScaleMode") ?? 0) == 1)
        {
            var refr = scaler.TryGetValue("m_ReferenceResolution", out var ro) ? ro as Dictionary<string, object> : null;
            float rw = MiniJson.Flt(refr, "x") ?? screen.x, rh = MiniJson.Flt(refr, "y") ?? screen.y;
            var mode = MiniJson.Flt(scaler, "m_ScreenMatchMode") ?? 0;
            if (mode == 1) k = Mathf.Min(screen.x / rw, screen.y / rh);
            else if (mode == 2) k = Mathf.Max(screen.x / rw, screen.y / rh);
            else
            {
                var m = MiniJson.Flt(scaler, "m_MatchWidthOrHeight") ?? 0;
                k = Mathf.Pow(2, (1 - m) * Mathf.Log(screen.x / rw, 2) + m * Mathf.Log(screen.y / rh, 2));
            }
        }
        else k = MiniJson.Flt(scaler, "m_ScaleFactor") ?? 1f;
        return screen / k;
    }

    // -- render --------------------------------------------------------------

    public static void RenderBatch()
    {
        var prefabPath = ImportExtracted.Arg("-cloneUiPrefab", "");
        var outPath = ImportExtracted.Arg("-cloneOut", "ui.png");
        var screen = ParseScreen(ImportExtracted.Arg("-cloneScreen", "1080x2400"));
        bool transparent = Array.IndexOf(Environment.GetCommandLineArgs(), "-cloneTransparent") >= 0;
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath), scene);
        var size = ((RectTransform)go.transform).sizeDelta;
        var cam = new GameObject("UICamera").AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = size.y / 2f;
        cam.transform.position = new Vector3(0, 0, -100);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = transparent ? new Color(0, 0, 0, 0) : new Color(0.1f, 0.1f, 0.12f, 1);
        cam.nearClipPlane = 0.1f; cam.farClipPlane = 1000f;
        int w = (int)screen.x, h = (int)screen.y;
        cam.aspect = (float)w / h;
        Canvas.ForceUpdateCanvases();
        foreach (var t in go.GetComponentsInChildren<TMP_Text>(true)) t.ForceMeshUpdate(true, true);
        var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4 };
        cam.targetTexture = rt;
        cam.Render();
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes(outPath, tex.EncodeToPNG());
        Console.WriteLine($"[ImportUI] rendered {Path.GetFileNameWithoutExtension(prefabPath)} {w}x{h} -> {outPath}");
        EditorApplication.Exit(0);
    }

    // -- verify --------------------------------------------------------------

    /// <summary>Every node's on-canvas box, bound sprite, text and active state against
    /// expected-ui.py (computed in Python from the dump). Boxes in canvas units, origin
    /// bottom-left; tolerance 0.5 unit.</summary>
    public static void VerifyBatch()
    {
        var prefabPath = ImportExtracted.Arg("-cloneUiPrefab", "");
        var expect = MiniJson.Parse(File.ReadAllText(ImportExtracted.Arg("-cloneExpect", ""))) as Dictionary<string, object>;
        var reportPath = ImportExtracted.Arg("-cloneReport", "verify-ui.json");
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath), scene);
        Canvas.ForceUpdateCanvases();
        var size = ((RectTransform)go.transform).sizeDelta;
        var byId = go.GetComponentsInChildren<ExtractedNode>(true).Where(t => t.nodeId != null)
                     .GroupBy(t => t.nodeId).ToDictionary(g => g.Key, g => g.First());
        var fails = new List<string>(); var counts = new Dictionary<string, int[]>();
        void Check(string node, string name, bool ok, string exp, string got)
        {
            if (!counts.TryGetValue(name, out var cc)) counts[name] = cc = new int[2];
            cc[ok ? 0 : 1]++;
            if (!ok) fails.Add($"{{\"node\": {Q(node)}, \"check\": {Q(name)}, \"expected\": {Q(exp)}, \"got\": {Q(got)}}}");
        }
        var corners = new Vector3[4];
        foreach (var o in MiniJson.Arr(expect, "nodes"))
        {
            var n = o as Dictionary<string, object>;
            var id = MiniJson.Str(n, "id"); var label = MiniJson.Str(n, "path");
            if (!byId.TryGetValue(id ?? "", out var tag)) { Check(label, "node exists", false, id, "missing"); continue; }
            Check(label, "node exists", true, null, null);
            var rt = tag.transform as RectTransform;
            var box = MiniJson.Floats(n.TryGetValue("box", out var bo) ? bo : null);
            if (rt != null && box.Count == 4)
            {
                rt.GetWorldCorners(corners);
                float x0 = corners.Min(p => p.x) + size.x / 2, y0 = corners.Min(p => p.y) + size.y / 2;
                float x1 = corners.Max(p => p.x) + size.x / 2, y1 = corners.Max(p => p.y) + size.y / 2;
                bool ok = Mathf.Abs(x0 - box[0]) < 0.5f && Mathf.Abs(y0 - box[1]) < 0.5f &&
                          Mathf.Abs(x1 - x0 - box[2]) < 0.5f && Mathf.Abs(y1 - y0 - box[3]) < 0.5f;
                Check(label, "box on canvas", ok, $"{box[0]:F1},{box[1]:F1} {box[2]:F1}x{box[3]:F1}",
                      $"{x0:F1},{y0:F1} {x1 - x0:F1}x{y1 - y0:F1}");
            }
            var sprite = MiniJson.Str(n, "sprite_file");
            if (sprite != null)
            {
                var im = tag.GetComponent<Image>();
                var got = im != null && im.sprite != null ? im.sprite.name : "none";
                Check(label, "bound sprite", got == Path.GetFileNameWithoutExtension(sprite), sprite, got);
            }
            var text = MiniJson.Str(n, "text");
            if (text != null)
            {
                var t = tag.GetComponent<TMP_Text>();
                Check(label, "text", t != null && t.text == text, text, t != null ? t.text : "none");
            }
            if (n.TryGetValue("active_self", out var ao) && ao is bool act)
                Check(label, "active", tag.gameObject.activeSelf == act, act.ToString(), tag.gameObject.activeSelf.ToString());
        }
        int failed = counts.Values.Sum(v => v[1]);
        File.WriteAllText(reportPath, "{\n \"checks\": {" + string.Join(",", counts.Select(kv =>
            $"\n  {Q(kv.Key)}: {{\"passed\": {kv.Value[0]}, \"failed\": {kv.Value[1]}}}")) +
            "\n },\n \"failures\": [" + string.Join(",", fails.Take(500).Select(f => "\n  " + f)) + "\n ]\n}\n");
        Console.WriteLine($"[ImportUI] verify {Path.GetFileNameWithoutExtension(prefabPath)}: {failed} failed checks -> {reportPath}");
        EditorApplication.Exit(failed > 0 ? 1 : 0);
    }

    // -- helpers -------------------------------------------------------------

    private static Vector2 ParseScreen(string s)
    {
        var p = s.ToLowerInvariant().Split('x');
        return new Vector2(float.Parse(p[0], System.Globalization.CultureInfo.InvariantCulture),
                           float.Parse(p[1], System.Globalization.CultureInfo.InvariantCulture));
    }

    private static Vector2 V2(Dictionary<string, object> d, string k, Vector2 fallback)
    {
        if (d == null || !d.TryGetValue(k, out var v) || v == null) return fallback;
        if (v is Dictionary<string, object> m) return new Vector2(MiniJson.Flt(m, "x") ?? fallback.x, MiniJson.Flt(m, "y") ?? fallback.y);
        var f = MiniJson.Floats(v);
        return f.Count >= 2 ? new Vector2(f[0], f[1]) : fallback;
    }

    private static Color Col(Dictionary<string, object> d, string k, Color fallback)
    {
        if (d == null || !d.TryGetValue(k, out var v) || !(v is Dictionary<string, object> m)) return fallback;
        if (m.ContainsKey("rgba")) { var u = Convert.ToUInt32(m["rgba"]); return new Color32((byte)(u & 255), (byte)((u >> 8) & 255), (byte)((u >> 16) & 255), (byte)(u >> 24)); }
        return new Color(MiniJson.Flt(m, "r") ?? fallback.r, MiniJson.Flt(m, "g") ?? fallback.g,
                         MiniJson.Flt(m, "b") ?? fallback.b, MiniJson.Flt(m, "a") ?? fallback.a);
    }

    private static string Q(string s) =>
        s == null ? "null" : "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n") + "\"";
}
#endif
