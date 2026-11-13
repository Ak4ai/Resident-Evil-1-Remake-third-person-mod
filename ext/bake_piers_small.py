# Fast partial bake: only the pier_* objects, into a small 512x512 image (Cycles cost scales with the image size), then the
# 128x128 blocks are pasted into the full 4096 lightmap layers (lm_layers/<layer>.npy) at the pier's lm UV block.
# blender -b blend/r105_lm.blend --python ext/bake_piers_small.py
import bpy, numpy as np, time, math
D = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\%s.npy'
FULL, SMALL, BLK = 4096, 512, 128
REG = [(64, 320), (64, 512), (64, 704), (320, 320), (320, 512), (320, 704), (704, 64), (704, 288), (704, 544), (896, 64), (896, 288), (896, 544)]
GROUPS = {'base': lambda n: n in ('lustre_W', 'lustre_E', 'lustre_alto', 'fill_leste', 'fundo_oeste', 'lua'),
          'lareira': lambda n: n == 'lareira', 'velas': lambda n: n.startswith('candelabro_'), 'arandelas': lambda n: n.startswith('arandela_')}
pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = 'OPTIX'; pr.get_devices()
for d in pr.devices: d.use = (d.type == 'OPTIX')
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 256; sc.cycles.use_denoising = False
b = sc.render.bake; b.use_pass_direct = True; b.use_pass_indirect = True; b.use_pass_color = False; b.target = 'IMAGE_TEXTURES'; b.margin = 4; b.use_clear = True
piers = sorted([o for o in bpy.data.objects if o.name.startswith('pier_')], key=lambda o: int(o.name.split('_')[1]))
blocks = []
for k, o in enumerate(piers):
    me = o.data; lm = me.uv_layers['lm']; uv = np.array([d.uv[:] for d in lm.data])
    r0, c0 = REG[k]                                               # exact block origin used by make_piers.py
    tr, tc = (k // 4) * BLK, (k % 4) * BLK                         # slot in the small image (4 x 3 blocks)
    t = me.uv_layers.get('lmtmp') or me.uv_layers.new(name='lmtmp')
    for i, d in enumerate(lm.data):
        u = uv[i, 0] * FULL - c0 + tc; v = uv[i, 1] * FULL - r0 + tr
        t.data[i].uv = (u / SMALL, v / SMALL)
    me.uv_layers.active = t; blocks.append((r0, c0, tr, tc))
img = bpy.data.images.new('pier_tmp', SMALL, SMALL, float_buffer=True, alpha=False)
mats = set(s.material for o in piers for s in o.material_slots if s.material)
for m in mats:
    nt = m.node_tree; n = nt.nodes.new('ShaderNodeTexImage'); n.image = img; nt.nodes.active = n
lights = list(bpy.data.collections['Luz_r105'].all_objects)
w = sc.world; bg = next((n for n in w.node_tree.nodes if n.type == 'BACKGROUND'), None); ws = bg.inputs['Strength'].default_value if bg else 0
for layer, f in GROUPS.items():
    t0 = time.time()
    for L in lights: L.hide_render = not f(L.name)
    if bg: bg.inputs['Strength'].default_value = ws if layer == 'base' else 0
    bpy.ops.object.select_all(action='DESELECT')
    for o in piers: o.select_set(True)
    bpy.context.view_layer.objects.active = piers[0]
    bpy.ops.object.bake(type='DIFFUSE')
    a = np.empty(SMALL * SMALL * 4, np.float32); img.pixels.foreach_get(a); a = a.reshape(SMALL, SMALL, 4)[:, :, :3]
    full = np.load(D % layer).astype(np.float32)
    for r0, c0, tr, tc in blocks: full[r0:r0 + BLK, c0:c0 + BLK] = a[tr:tr + BLK, tc:tc + BLK]
    np.save(D % layer, full.astype(np.float16))
    print('LAYER', layer, 'sec', round(time.time() - t0), 'max', float(a.max()), flush=True)
for o in piers:
    o.data.uv_layers.remove(o.data.uv_layers['lmtmp'])
print('DONE')
