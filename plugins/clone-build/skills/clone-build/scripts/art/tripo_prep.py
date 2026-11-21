# tripo_prep.py — prepare an image-to-3D GLB (Tripo and similar) for the game KEEPING its painted texture: join parts, put the
# base at z 0 and centre it, weld, decimate to a face budget, keep UV and the texture (downscaled). Flattening the painted
# texture into a few role colours removed the soft shading and wood/stone grain and made the model look cheap.
#   blender -b --python tripo_prep.py -- <in.glb> <out.obj> <face budget> <texture size>
# Checked on Blender 5.2 with a real textured GLB (8k faces, 512 px texture written). A GLB exported without texture exits
# with a message: regenerate it with texture on.
import bpy, os, sys
from mathutils import Matrix, Vector
a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT, FACES, TEX = a[0], a[1], int(a[2]), int(a[3])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
ms = [o for o in bpy.context.scene.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in ms: o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1: bpy.ops.object.join()
o = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
lo = Vector([min(v.co[i] for v in o.data.vertices) for i in range(3)]); hi = Vector([max(v.co[i] for v in o.data.vertices) for i in range(3)])
o.data.transform(Matrix.Translation(Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))))
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT"); bpy.ops.mesh.remove_doubles(threshold=1e-5)
bpy.ops.object.mode_set(mode="OBJECT")
if len(o.data.polygons) > FACES:
    md = o.modifiers.new("decimate", "DECIMATE"); md.ratio = FACES / len(o.data.polygons); bpy.ops.object.modifier_apply(modifier=md.name)
for p in o.data.polygons: p.use_smooth = True
img = next((n.image for m in o.data.materials if m and m.node_tree for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
if img is None:
    sys.exit("tripo_prep: the GLB has no image texture — export it with texture on")
img.scale(TEX, TEX)  # GLB textures arrive packed; write the scaled pixels out explicitly
tex = os.path.splitext(OUT)[0] + "_tex.png"
img.filepath_raw = tex; img.file_format = "PNG"
if img.packed_file:
    img.unpack(method="REMOVE")
img.save()
if not os.path.exists(tex):
    sys.exit("tripo_prep: texture was not written to " + tex)
for m in o.data.materials: m.name = "Tex"
o.name = o.data.name = "Body"
bpy.ops.object.select_all(action="DESELECT"); o.select_set(True)
bpy.ops.wm.obj_export(filepath=OUT, export_selected_objects=True, export_materials=False, export_normals=True, export_uv=True,
                      forward_axis="NEGATIVE_Z", up_axis="Y")
print("READY", len(o.data.polygons), "faces", [round(c, 3) for c in (hi - lo)])
