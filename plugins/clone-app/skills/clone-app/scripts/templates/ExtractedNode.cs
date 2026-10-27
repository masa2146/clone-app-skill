// ExtractedNode.cs — runtime components the clone-app importer puts on rebuilt prefabs.
//
// Must live OUTSIDE an Editor folder: Unity refuses to add a component whose
// script sits in an Editor assembly, and the prefab then never saves.
using UnityEngine;

/// <summary>Which extracted node this GameObject was built from. VerifyImport.cs
/// maps every built object back to its entity.json node through this.</summary>
public class ExtractedNode : MonoBehaviour
{
    public string nodeId;
    public int nodeIndex;
}

/// <summary>Source entity and the original script names to reimplement.</summary>
public class ExtractedEntityNote : MonoBehaviour
{
    [TextArea(2, 12)] public string sourceEntity;
    [TextArea(2, 12)] public string originalScripts;
    [TextArea(2, 12)] public string notes;
}
