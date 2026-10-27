// RenderLayout.cs — place rebuilt prefabs as a layout describes and render one frame.
//
//   Unity -batchmode -projectPath <p> -executeMethod RenderLayout.Run -cloneLayout layout.json -quit
//   (no -nographics: rendering needs the GPU)
//
// layout.json (all positions/rotations in world space, rotations as x,y,z,w):
//   {"width": 1080, "height": 2400, "out": "/abs/frame.png", "prefabs": "Assets/Extracted/Prefabs",
//    "background": [r,g,b],
//    "camera": {"position": [..], "rotation": [..], "fov": 30, "near": 0.3, "far": 1000,
//               "orthographic": false, "size": 5},
//    "lights": [{"rotation": [..], "color": [r,g,b,a], "intensity": 1}],
//    "objects": [{"prefab": "Name", "position": [..], "rotation": [..], "scale": [..]}]}
//
// This is how a rebuild is put next to the original: the same level, the same
// camera, one frame each. Unknown prefabs are listed, never silently skipped.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class RenderLayout
{
    public static void Run()
    {
        var path = ImportExtracted.Arg("-cloneLayout", "");
        var L = MiniJson.Parse(File.ReadAllText(path)) as Dictionary<string, object>;
        int w = (int)(MiniJson.Flt(L, "width") ?? 1080), h = (int)(MiniJson.Flt(L, "height") ?? 2400);
        var outPath = MiniJson.Str(L, "out") ?? "layout.png";
        var prefabDir = MiniJson.Str(L, "prefabs") ?? "Assets/Extracted/Prefabs";

        // SRP Batcher painted a URP scene one flat colour once an incompatible material
        // joined it; a verification frame trades batching for correctness
        UnityEngine.Rendering.GraphicsSettings.useScriptableRenderPipelineBatching = false;
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var missing = new SortedDictionary<string, int>();
        int placed = 0;
        foreach (var o in MiniJson.Arr(L, "objects"))
        {
            var d = o as Dictionary<string, object>;
            var name = MiniJson.Str(d, "prefab");
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{prefabDir}/{ImportExtracted.SafeName(name)}.prefab");
            if (prefab == null) { missing[name] = missing.TryGetValue(name, out var c) ? c + 1 : 1; continue; }
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
            var p = MiniJson.Vec(d, "position");
            var q = MiniJson.Floats(d.TryGetValue("rotation", out var qv) ? qv : null);
            var s = MiniJson.Vec(d, "scale");
            if (p != null) go.transform.position = p.Value;
            if (q.Count >= 4) go.transform.rotation = new Quaternion(q[0], q[1], q[2], q[3]);
            if (s != null) go.transform.localScale = s.Value;
            placed++;
        }

        var camSpec = L.TryGetValue("camera", out var co) ? co as Dictionary<string, object> : null;
        var cam = new GameObject("LayoutCamera").AddComponent<Camera>();
        var bg = MiniJson.Floats(L.TryGetValue("background", out var bgv) ? bgv : null);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = bg.Count >= 3 ? new Color(bg[0], bg[1], bg[2]) : new Color(0.5f, 0.5f, 0.5f);
        if (camSpec != null)
        {
            var cp = MiniJson.Vec(camSpec, "position");
            var cq = MiniJson.Floats(camSpec.TryGetValue("rotation", out var cqv) ? cqv : null);
            if (cp != null) cam.transform.position = cp.Value;
            if (cq.Count >= 4) cam.transform.rotation = new Quaternion(cq[0], cq[1], cq[2], cq[3]);
            cam.orthographic = MiniJson.Bool(camSpec, "orthographic");
            cam.fieldOfView = MiniJson.Flt(camSpec, "fov") ?? 60f;
            cam.orthographicSize = MiniJson.Flt(camSpec, "size") ?? 5f;
            cam.nearClipPlane = MiniJson.Flt(camSpec, "near") ?? 0.3f;
            cam.farClipPlane = MiniJson.Flt(camSpec, "far") ?? 1000f;
        }
        foreach (var lo in MiniJson.Arr(L, "lights"))
        {
            var ld = lo as Dictionary<string, object>;
            var light = new GameObject("LayoutLight").AddComponent<Light>();
            light.type = LightType.Directional;
            var lq = MiniJson.Floats(ld.TryGetValue("rotation", out var lqv) ? lqv : null);
            if (lq.Count >= 4) light.transform.rotation = new Quaternion(lq[0], lq[1], lq[2], lq[3]);
            var lc = MiniJson.Floats(ld.TryGetValue("color", out var lcv) ? lcv : null);
            if (lc.Count >= 3) light.color = new Color(lc[0], lc[1], lc[2]);
            light.intensity = MiniJson.Flt(ld, "intensity") ?? 1f;
        }
        cam.aspect = (float)w / h;

        var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4 };
        cam.targetTexture = rt;
        cam.Render();
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes(outPath, tex.EncodeToPNG());
        Console.WriteLine($"[RenderLayout] placed {placed}, missing {missing.Count} prefab(s)" +
                          (missing.Count > 0 ? ": " + string.Join(", ", missing.Select(m => $"{m.Key} x{m.Value}")) : "") +
                          $" -> {outPath}");
        EditorApplication.Exit(0);
    }
}
#endif
