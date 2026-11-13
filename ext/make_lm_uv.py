# Headless: blender -b blend/r105_work.blend --python ext/make_lm_uv.py
# Builds a proper lightmap UV ('lm') on the CLEAN (non-subdivided) geometry: modifiers applied, curves -> meshes,
# single-user data, smart-project islands packed globally across all objects. Saves blend/r105_lm.blend.
import bpy, time, math
t0 = time.time()
objs = [o for c in ('Fit_Dining', 'Props') for o in bpy.data.collections[c].all_objects
        if o.type in ('MESH', 'CURVE') and not o.hide_render]
print('LMUV objs', len(objs))
bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.hide_set(False); o.hide_viewport = False; o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False)
bpy.ops.object.convert(target='MESH')
meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH' and len(o.data.polygons)]
print('LMUV meshes', len(meshes), 'faces', sum(len(o.data.polygons) for o in meshes))
for o in meshes:
    for u in list(o.data.uv_layers):
        if u.name in ('lm', 'luz'): o.data.uv_layers.remove(u)
    lm = o.data.uv_layers.new(name='lm'); o.data.uv_layers.active = lm
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(80), island_margin=0.0004, area_weight=0.6, correct_aspect=True, scale_to_bounds=False)
bpy.context.scene.tool_settings.use_uv_select_sync = True
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.pack_islands(udim_source='ACTIVE_UDIM', rotate=True, margin=0.0004, scale=True, merge_overlap=False, shape_method='AABB')
bpy.ops.object.mode_set(mode='OBJECT')
# coverage report
import numpy as np
tot = 0.0; n = 0
for o in meshes:
    lm = o.data.uv_layers['lm']
    uv = np.array([d.uv[:] for d in lm.data]); n += len(uv)
    if len(uv) and (uv.min() < -0.001 or uv.max() > 1.001): print('LMUV out of range', o.name, uv.min(), uv.max())
print('LMUV loops', n)
bpy.ops.wm.save_as_mainfile(filepath=r'C:\Users\HENRIQUE\Tools\re1mod\blend\r105_lm.blend')
print('LMUV done sec', round(time.time() - t0))
