# Headless: blender -b blend/r105_lm.blend --python ext/preview_lm.py -- cam01 cam03 ...
# Emulates the game's RMS4 shading inside Blender WITHOUT any bake: emission = albedo * lightmap, where the lightmap is the
# 4 baked layers decoded exactly like the game (8-bit gamma-2 PNG round trip, weights, ambient, tonemap). Writes preview/lm_<cam>.png.
# Nothing is saved to the .blend.
import bpy, sys, re, numpy as np, time
names = sys.argv[sys.argv.index('--') + 1:]
AMB, TONE, EXPO = 0.08, 2.0, 1.4
W = {'base': 1.0, 'lareira': 1.0, 'velas': 1.0, 'arandelas': 0.45}
D = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\%s.npy'
acc = None
for k, w in W.items():
    a = np.load(D % k).astype(np.float32)
    q = np.round(np.clip(a / 4.0, 0, 1) ** 0.5 * 255) / 255      # what the 8-bit PNG stores
    x = (q * q) * 4.0 * w                                          # what the shader decodes
    acc = x if acc is None else acc + x
L = acc + AMB
L = L * (1 + TONE) / (1 + TONE * L)                                # tonemap, linear (game then applies ^0.4545 and multiplies in gamma space)
H = L.shape[0]
img = bpy.data.images.new('lm_game', H, H, float_buffer=True, alpha=False)
img.colorspace_settings.name = 'Non-Color'
px = np.ones((H, H, 4), np.float32); px[:, :, :3] = L
img.pixels.foreach_set(px.ravel()); img.update()
del acc, L, px

def base_image(m):
    nt = m.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b and b.inputs['Base Color'].is_linked:
        n = b.inputs['Base Color'].links[0].from_node
        for _ in range(4):
            if n.type == 'TEX_IMAGE': return n.image
            ins = [i for i in n.inputs if i.is_linked]
            if not ins: break
            n = ins[0].links[0].from_node
    t = [n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image]
    pref = [n for n in t if re.search(r'(_bm|albd|diff|color|col)', n.image.name, re.I)]
    return (pref or t or [None])[0].image if (pref or t) else None

mats = set()
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for u in o.data.uv_layers:
        if u.name != 'lm': u.active_render = True; break
    for s in o.material_slots:
        if s.material: mats.add(s.material)
fac = EXPO ** 2.2                                                  # expo multiplies in gamma space -> ^2.2 in linear
for m in mats:
    m.use_nodes = True; nt = m.node_tree
    bi = base_image(m)
    bc = (1, 1, 1, 1)
    pb = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if pb: bc = tuple(pb.inputs['Base Color'].default_value)
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None) or nt.nodes.new('ShaderNodeOutputMaterial')
    lm = nt.nodes.new('ShaderNodeTexImage'); lm.image = img; lm.interpolation = 'Linear'; lm.extension = 'EXTEND'
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'lm'; nt.links.new(uv.outputs[0], lm.inputs[0])
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    if bi:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = bi; nt.links.new(t.outputs['Color'], mul.inputs[6])
    else:
        mul.inputs[6].default_value = bc
    nt.links.new(lm.outputs['Color'], mul.inputs[7])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = fac
    nt.links.new(mul.outputs[2], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])

pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = 'OPTIX'; pr.get_devices()
for d in pr.devices: d.use = (d.type == 'OPTIX')
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 4
sc.cycles.use_denoising = False; sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
sc.render.resolution_x = 640; sc.render.resolution_y = 480; sc.render.resolution_percentage = 100
for n in names:
    o = bpy.data.objects.get(n)
    if not o: print('NOCAM', n); continue
    sc.camera = o; t = time.time(); sc.render.filepath = r'C:\Users\HENRIQUE\Tools\re1mod\preview\lm_%s.png' % n
    bpy.ops.render.render(write_still=True); print('RENDER', n, round(time.time() - t, 1), flush=True)
