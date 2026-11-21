# tripo_prep.py — prepare an image-to-3D GLB (Tripo and similar) for the game KEEPING its painted texture: join parts, put the
# base at z 0 and centre it, weld, decimate to a face budget, keep UV and the texture (downscaled). Flattening the painted
# texture into a few role colours removed the soft shading and wood/stone grain and made the model look cheap.
#   blender -b --python tripo_prep.py -- <in.glb> <out.obj> <face budget> <texture size>
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
img = next(n.image for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image)
img.scale(TEX, TEX); img.filepath_raw = os.path.splitext(OUT)[0] + "_tex.png"; img.file_format = "PNG"; img.save()
for m in o.data.materials: m.name = "Tex"
o.name = o.data.name = "Body"
bpy.ops.object.select_all(action="DESELECT"); o.select_set(True)
bpy.ops.wm.obj_export(filepath=OUT, export_selected_objects=True, export_materials=False, export_normals=True, export_uv=True,
                      forward_axis="NEGATIVE_Z", up_axis="Y")
print("READY", len(o.data.polygons), "faces", [round(c, 3) for c in (hi - lo)])
