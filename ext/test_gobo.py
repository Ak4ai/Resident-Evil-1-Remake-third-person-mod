# Root-cause test for the light blobs: top-down ortho view of the floor (camera just below the mezzanine), selected lights only.
# Usage: blender -b blend/r105_lm.blend --python ext/test_gobo.py -- lustre_W,lustre_E,lustre_alto 2.9
# A) as is   B) objects close to a light cast no shadow   C) as A but light radius 0
import bpy, mathutils, sys
R = 0.8
OUT = r'C:\Users\HENRIQUE\Tools\re1mod\preview\gobo_%s.png'
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ON = args[0].split(',') if args else ['lustre_W', 'lustre_E', 'lustre_alto']
Z = float(args[1]) if len(args) > 1 else 2.9
pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = 'OPTIX'; pr.get_devices()
for d in pr.devices: d.use = (d.type == 'OPTIX')
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 32; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'
lights = [L for L in bpy.data.collections['Luz_r105'].all_objects if L.type == 'LIGHT']
near = set()
for o in bpy.data.objects:
    if o.type != 'MESH' or o.hide_render: continue
    bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    lo = mathutils.Vector([min(v[i] for v in bb) for i in range(3)]); hi = mathutils.Vector([max(v[i] for v in bb) for i in range(3)])
    for L in lights:
        if L.name not in ON: continue
        p = L.matrix_world.translation; q = mathutils.Vector([min(max(p[i], lo[i]), hi[i]) for i in range(3)])
        if (q - p).length < R and (hi - lo).length < 4.0: near.add(o.name)
print('FIXTURES', sorted(n[:30] for n in near))
for L in lights: L.hide_render = L.name not in ON
w = sc.world; bg = next((n for n in w.node_tree.nodes if n.type == 'BACKGROUND'), None)
if bg: bg.inputs['Strength'].default_value = 0
cd = bpy.data.cameras.new('floorcam'); cd.type = 'ORTHO'; cd.ortho_scale = 20.5; cd.clip_start = 0.05; cd.clip_end = 10
cam = bpy.data.objects.new('floorcam', cd); sc.collection.objects.link(cam); cam.location = (0, 0, Z); cam.rotation_euler = (0, 0, 0)
sc.camera = cam; sc.render.resolution_x = 1000; sc.render.resolution_y = 360
sc.render.filepath = OUT % 'A'; bpy.ops.render.render(write_still=True)
for n in near: bpy.data.objects[n].visible_shadow = False
sc.render.filepath = OUT % 'B'; bpy.ops.render.render(write_still=True)
for n in near: bpy.data.objects[n].visible_shadow = True
for L in lights:
    if L.name in ON: L.data.shadow_soft_size = 0.0
sc.render.filepath = OUT % 'C'; bpy.ops.render.render(write_still=True)
print('DONE')
