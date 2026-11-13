# Partial lightmap re-bake for a few objects (default: the chairs ch_*), without touching the rest of the atlas.
# 1) optional: push the upholstery (yg_fabric_01) 4 mm out along the normals so it no longer touches the frame panel
# 2) temporary UV 'lmtmp' (smart project, packed) -> bake the 4 light groups into a 1024^2 image (fast)
# 3) dump per-triangle (lm uv, lmtmp uv) + the 4 baked images to lm_layers/partial_bake.npz; ext/apply_partial_bake.py
#    then re-samples them into the 4096 atlas texels of those triangles.
# blender -b blend/r105_lm.blend --python ext/bake_objs_partial.py -- ch_ [push]
import bpy, bmesh, numpy as np, sys, time, math
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PREFIX = args[0] if args else 'ch_'; PUSH = 'push' in args
TMP = 1024
GROUPS = {'base': lambda n: n in ('lustre_W', 'lustre_E', 'lustre_alto', 'fill_leste', 'fundo_oeste', 'lua'),
          'lareira': lambda n: n == 'lareira', 'velas': lambda n: n.startswith('candelabro_'), 'arandelas': lambda n: n.startswith('arandela_')}
objs = [o for o in bpy.data.objects if o.name.startswith(PREFIX) and o.type == 'MESH' and not o.hide_render and o.data.uv_layers.get('lm')]
print('OBJS', len(objs))
if PUSH:
    for o in objs:
        me = o.data; bm = bmesh.new(); bm.from_mesh(me)
        fi = [i for i, s in enumerate(o.material_slots) if s.material and 'fabric' in s.material.name]
        vs = set(v for f in bm.faces if f.material_index in fi for v in f.verts)
        for v in vs: v.co += v.normal * 0.004
        bm.to_mesh(me); bm.free(); me.update()
    bpy.ops.wm.save_mainfile()
    print('PUSHED fabric 4 mm')
for o in objs:
    t = o.data.uv_layers.get('lmtmp') or o.data.uv_layers.new(name='lmtmp'); o.data.uv_layers.active = t
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(70), island_margin=0.004, scale_to_bounds=False)
bpy.context.scene.tool_settings.use_uv_select_sync = True
bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
bpy.ops.object.mode_set(mode='OBJECT')
pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = 'OPTIX'; pr.get_devices()
for d in pr.devices: d.use = (d.type == 'OPTIX')
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 256; sc.cycles.use_denoising = False
b = sc.render.bake; b.use_pass_direct = True; b.use_pass_indirect = True; b.use_pass_color = False; b.target = 'IMAGE_TEXTURES'; b.margin = 4; b.use_clear = True
img = bpy.data.images.new('part_tmp', TMP, TMP, float_buffer=True, alpha=False)
for m in set(s.material for o in objs for s in o.material_slots if s.material):
    n = m.node_tree.nodes.new('ShaderNodeTexImage'); n.image = img; m.node_tree.nodes.active = n
lights = list(bpy.data.collections['Luz_r105'].all_objects)
w = sc.world; bg = next((n for n in w.node_tree.nodes if n.type == 'BACKGROUND'), None); ws = bg.inputs['Strength'].default_value if bg else 0
out = {}
for layer, f in GROUPS.items():
    t0 = time.time()
    for L in lights: L.hide_render = not f(L.name)
    if bg: bg.inputs['Strength'].default_value = ws if layer == 'base' else 0
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type='DIFFUSE')
    a = np.empty(TMP * TMP * 4, np.float32); img.pixels.foreach_get(a); out[layer] = a.reshape(TMP, TMP, 4)[:, :, :3].astype(np.float16)
    print('LAYER', layer, 'sec', round(time.time() - t0), flush=True)
LM = []; TM = []
for o in objs:
    me = o.data; me.calc_loop_triangles(); lm = me.uv_layers['lm']; tm = me.uv_layers['lmtmp']
    for t in me.loop_triangles:
        LM.append([lm.data[l].uv[:] for l in t.loops]); TM.append([tm.data[l].uv[:] for l in t.loops])
np.savez(r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\partial_bake.npz', LM=np.array(LM, np.float32), TM=np.array(TM, np.float32), **out)
for o in objs: o.data.uv_layers.remove(o.data.uv_layers['lmtmp'])
print('DONE tris', len(LM))
