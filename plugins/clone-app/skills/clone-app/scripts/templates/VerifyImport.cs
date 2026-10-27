// VerifyImport.cs — prove the rebuilt prefabs match the extraction, node by node.
//
//   python3 <clone-app>/scripts/expected-import.py <game-assets> > expect.json
//   Unity -batchmode -projectPath <p> -executeMethod VerifyImport.Run \
//         -cloneExpect expect.json [-cloneTarget Assets/Extracted] [-cloneReport report.json] -quit
//
// expect.json is computed from the extracted files in Python, independently of the
// importer. For every node this checks: it exists, its parent, its local
// position/rotation/scale, the triangle count of every sub-mesh, the mesh's own
// box, the mesh's box in the entity root's space (catches a part shifted, mirrored
// or scaled), the material on each slot (by extracted id), the collider types and
// the rigidbody mass. Exit code 1 when any check fails.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class VerifyImport
{
    private class Failure { public string entity, node, check, expected, got; }

    public static void Run()
    {
        var expectPath = ImportExtracted.Arg("-cloneExpect", "");
        var target = ImportExtracted.Arg("-cloneTarget", "Assets/Extracted");
        var reportPath = ImportExtracted.Arg("-cloneReport", "verify-report.json");
        var expect = MiniJson.Parse(File.ReadAllText(expectPath)) as Dictionary<string, object>;
        var entities = expect?["entities"] as Dictionary<string, object> ?? new Dictionary<string, object>();

        var fails = new List<Failure>();
        var checks = new Dictionary<string, int[]>();   // check -> {passed, failed}
        int entitiesOk = 0, nodesOk = 0, nodesTotal = 0;

        foreach (var kv in entities)
        {
            var ent = kv.Value as Dictionary<string, object>;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(
                $"{target}/Prefabs/{ImportExtracted.SafeName(kv.Key)}.prefab");
            int before = fails.Count;
            void Check(string node, string name, bool ok, string exp, string got)
            {
                if (!checks.TryGetValue(name, out var c)) checks[name] = c = new int[2];
                c[ok ? 0 : 1]++;
                if (!ok) fails.Add(new Failure { entity = kv.Key, node = node, check = name, expected = exp, got = got });
            }
            if (prefab == null)
            {
                Check("-", "prefab exists", false, "prefab", "none");
                continue;
            }
            var byId = new Dictionary<string, Transform>();
            foreach (var t in prefab.GetComponentsInChildren<ExtractedNode>(true))
                if (!string.IsNullOrEmpty(t.nodeId)) byId[t.nodeId] = t.transform;
            var root = prefab.transform;

            foreach (var o in MiniJson.Arr(ent, "nodes"))
            {
                var n = o as Dictionary<string, object>;
                var id = MiniJson.Str(n, "id");
                var label = $"{MiniJson.Str(n, "name")} #{id}";
                nodesTotal++;
                int nodeBefore = fails.Count;
                if (!byId.TryGetValue(id ?? "", out var tr))
                {
                    Check(label, "node exists", false, id, "missing");
                    continue;
                }
                Check(label, "node exists", true, null, null);

                var pid = MiniJson.Str(n, "parent_id");
                var pTag = tr == root || tr.parent == null ? null : tr.parent.GetComponent<ExtractedNode>();
                var gotParent = pTag != null ? pTag.nodeId : null;
                Check(label, "parent", pid == gotParent, pid ?? "(root)", gotParent ?? "(root)");

                var lp = MiniJson.Vec(n, "localPosition");
                if (lp != null)
                    Check(label, "local position", (tr.localPosition - lp.Value).magnitude < 1e-4f,
                          lp.Value.ToString("F4"), tr.localPosition.ToString("F4"));
                var ls = MiniJson.Vec(n, "localScale");
                if (ls != null)
                    Check(label, "local scale", (tr.localScale - ls.Value).magnitude < 1e-4f,
                          ls.Value.ToString("F4"), tr.localScale.ToString("F4"));
                var q = MiniJson.Floats(n.TryGetValue("localRotation", out var qv) ? qv : null);
                if (q.Count >= 4)
                {
                    var eq = new Quaternion(q[0], q[1], q[2], q[3]).normalized;
                    Check(label, "local rotation", Mathf.Abs(Quaternion.Dot(eq, tr.localRotation)) > 0.99999f,
                          eq.eulerAngles.ToString("F2"), tr.localRotation.eulerAngles.ToString("F2"));
                }

                var tris = MiniJson.Floats(n.TryGetValue("triangles", out var tv) ? tv : null);
                if (n.ContainsKey("missing_mesh_file"))
                    Check(label, "mesh file shipped", false, MiniJson.Str(n, "missing_mesh_file"), "absent");
                if (tris.Count > 0)
                {
                    var mf = tr.GetComponent<MeshFilter>();
                    var mesh = mf != null ? mf.sharedMesh : null;
                    Check(label, "mesh present", mesh != null, "mesh", "none");
                    if (mesh != null)
                    {
                        var got = Enumerable.Range(0, mesh.subMeshCount)
                            .Select(s => (int)(mesh.GetIndexCount(s) / 3)).ToList();
                        var exp = tris.Select(x => (int)x).ToList();
                        Check(label, "triangles per sub-mesh", got.SequenceEqual(exp),
                              string.Join(",", exp), string.Join(",", got));
                        var mb = MiniJson.Floats(n.TryGetValue("mesh_box", out var mbv) ? mbv : null);
                        if (mb.Count == 6)
                            Check(label, "mesh box", BoxClose(mesh.bounds.min, mesh.bounds.max, mb),
                                  Fmt(mb), Fmt(mesh.bounds.min, mesh.bounds.max));
                        var rb = MiniJson.Floats(n.TryGetValue("root_box", out var rbv) ? rbv : null);
                        if (rb.Count == 6)
                        {
                            RootBox(mesh.bounds, tr, root, out var lo, out var hi);
                            Check(label, "box in root space", BoxClose(lo, hi, rb), Fmt(rb), Fmt(lo, hi));
                        }
                        var mr = tr.GetComponent<MeshRenderer>();
                        var expMats = MiniJson.Arr(n, "material_ids").Select(x => Convert.ToString(x)).ToList();
                        if (expMats.Count > 0 && mr != null)
                        {
                            var gotMats = mr.sharedMaterials.Select(m => m == null ? "null" :
                                Path.GetFileNameWithoutExtension(AssetDatabase.GetAssetPath(m))).ToList();
                            var expNames = expMats.Select(x => x == null ? "null" : ImportExtracted.MaterialAssetName(x)).ToList();
                            Check(label, "material per slot", gotMats.SequenceEqual(expNames),
                                  string.Join(",", expNames), string.Join(",", gotMats));
                        }
                    }
                }
                var spriteFile = MiniJson.Str(n, "sprite_file");
                if (!string.IsNullOrEmpty(spriteFile))
                {
                    var sr = tr.GetComponent<SpriteRenderer>();
                    // Unity's destroyed/missing objects are not C# null: no ?. on them
                    var gotSprite = sr != null && sr.sprite != null ? sr.sprite.name : "none";
                    Check(label, "sprite present", gotSprite != "none", spriteFile, gotSprite);
                }
                var builtin = MiniJson.Str(n, "builtin_mesh");
                if (!string.IsNullOrEmpty(builtin) && !builtin.StartsWith("unknown"))
                {
                    var bmf = tr.GetComponent<MeshFilter>();
                    var gotMesh = bmf != null && bmf.sharedMesh != null ? bmf.sharedMesh : null;
                    Check(label, "built-in mesh", gotMesh != null && gotMesh == ImportExtracted.BuiltinMesh(builtin),
                          builtin, gotMesh != null ? gotMesh.name : "none");
                }
                var cols = MiniJson.Arr(n, "colliders").Select(x => Convert.ToString(x)).OrderBy(x => x).ToList();
                var gotCols = tr.GetComponents<Collider>().Select(c => c.GetType().Name).OrderBy(x => x).ToList();
                Check(label, "colliders", cols.SequenceEqual(gotCols), string.Join(",", cols), string.Join(",", gotCols));
                var mass = MiniJson.Flt(n, "mass");
                var body = tr.GetComponent<Rigidbody>();
                Check(label, "rigidbody mass",
                      mass == null ? body == null : body != null && Mathf.Abs(body.mass - mass.Value) < 1e-4f,
                      mass?.ToString("F3") ?? "none", body != null ? body.mass.ToString("F3") : "none");
                if (fails.Count == nodeBefore) nodesOk++;
            }
            if (fails.Count == before) entitiesOk++;
        }

        var sb = new System.Text.StringBuilder();
        sb.Append("{\n \"entities\": ").Append(entities.Count)
          .Append(",\n \"entities_ok\": ").Append(entitiesOk)
          .Append(",\n \"nodes\": ").Append(nodesTotal)
          .Append(",\n \"nodes_ok\": ").Append(nodesOk)
          .Append(",\n \"checks\": {");
        sb.Append(string.Join(",", checks.Select(c => $"\n  {Q(c.Key)}: {{\"passed\": {c.Value[0]}, \"failed\": {c.Value[1]}}}")));
        sb.Append("\n },\n \"failures\": [");
        sb.Append(string.Join(",", fails.Take(2000).Select(f =>
            $"\n  {{\"entity\": {Q(f.entity)}, \"node\": {Q(f.node)}, \"check\": {Q(f.check)}, " +
            $"\"expected\": {Q(f.expected)}, \"got\": {Q(f.got)}}}")));
        sb.Append("\n ]\n}\n");
        File.WriteAllText(reportPath, sb.ToString());
        Console.WriteLine($"[VerifyImport] entities {entitiesOk}/{entities.Count} ok, nodes {nodesOk}/{nodesTotal} ok, " +
                          $"{fails.Count} failed checks -> {reportPath}");
        EditorApplication.Exit(fails.Count > 0 ? 1 : 0);
    }

    private static void RootBox(Bounds b, Transform node, Transform root, out Vector3 lo, out Vector3 hi)
    {
        lo = Vector3.positiveInfinity; hi = Vector3.negativeInfinity;
        for (int i = 0; i < 8; i++)
        {
            var c = new Vector3((i & 1) == 0 ? b.min.x : b.max.x, (i & 2) == 0 ? b.min.y : b.max.y,
                                (i & 4) == 0 ? b.min.z : b.max.z);
            // root-local space: the chain below the root, without the root's own TRS
            var p = root.InverseTransformPoint(node.TransformPoint(c));
            lo = Vector3.Min(lo, p); hi = Vector3.Max(hi, p);
        }
    }

    private static bool BoxClose(Vector3 lo, Vector3 hi, List<float> e)
    {
        float size = Mathf.Max(1e-3f, Mathf.Max(e[3] - e[0], Mathf.Max(e[4] - e[1], e[5] - e[2])));
        float tol = Mathf.Max(1e-4f, size * 1e-3f);
        return Mathf.Abs(lo.x - e[0]) < tol && Mathf.Abs(lo.y - e[1]) < tol && Mathf.Abs(lo.z - e[2]) < tol &&
               Mathf.Abs(hi.x - e[3]) < tol && Mathf.Abs(hi.y - e[4]) < tol && Mathf.Abs(hi.z - e[5]) < tol;
    }

    private static string Fmt(List<float> e) =>
        $"({e[0]:F3},{e[1]:F3},{e[2]:F3})-({e[3]:F3},{e[4]:F3},{e[5]:F3})";

    private static string Fmt(Vector3 lo, Vector3 hi) =>
        $"({lo.x:F3},{lo.y:F3},{lo.z:F3})-({hi.x:F3},{hi.y:F3},{hi.z:F3})";

    private static string Q(string s) =>
        s == null ? "null" : "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", " ") + "\"";
}
#endif
