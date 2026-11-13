# Headless: blender -b blend/r105_lm.blend --python ext/preview_rms4.py -- cam16 ...
# A/B test of the EXPORT: loads captures/r105_lm.rms4 (exactly what the game loads) into Blender, hides the original geometry,
# shades each part as emission = albedo png * decoded lightmap (same decode as preview_lm.py), renders the given cameras.
# If artefacts appear here but not in preview_lm.py, the exporter is at fault; if not, the game's render path is.
import bpy, sys, struct, numpy as np, os, time
names = sys.argv[sys.argv.index('--') + 1:]
LMONLY = bool(names and names[0] == 'lmonly')
if LMONLY: names = names[1:]
CAP = r'C:\Users\HENRIQUE\Tools\captures'
AMB, TONE, EXPO = 0.08, 2.0, 1.4
import os
W = {k: float(v) for k, v in (x.split(':') for x in os.environ['LAYERS'].split(','))} if os.environ.get('LAYERS') else {'base': 1.0, 'lareira': 1.0, 'velas': 1.0, 'arandelas': 0.45}
acc = None
for k, w in W.items():
    a = np.load(r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\%s.npy' % k).astype(np.float32)
    q = np.round(np.clip(a / 4.0, 0, 1) ** 0.5 * 255) / 255
    x = q * q * 4.0 * w; acc = x if acc is None else acc + x
L = acc + AMB; L = L * (1 + TONE) / (1 + TONE * L)  # GAMMA_DISPLAY
if LMONLY: L = np.power(np.maximum(L, 1e-5), 0.4545) ** 2.2  # game shows pow(L,.4545) as display value; image is linear
H = L.shape[0]
img = bpy.data.images.new('lm_game', H, H, float_buffer=True, alpha=False); img.colorspace_settings.name = 'Non-Color'
px = np.ones((H, H, 4), np.float32); px[:, :, :3] = L; img.pixels.foreach_set(px.ravel()); img.update(); del acc, L, px

for c in ('Fit_Dining', 'Props'):
    for o in bpy.data.collections[c].all_objects:
        if o: o.hide_render = True
col = bpy.data.collections.new('rms4'); bpy.context.scene.collection.children.link(col)
d = open(CAP + r'\r105_lm.rms4', 'rb').read()
assert d[:4] == b'RMS4'; npart = struct.unpack_from('<I', d, 4)[0]; off = 72
fac = 1.0 if LMONLY else EXPO ** 2.2
for i in range(npart):
    tex = d[off:off + 64].split(b'\0')[0].decode(); off += 64
    nv, nf = struct.unpack_from('<II', d, off); off += 8
    vb = np.frombuffer(d, dtype=[('p', '<f4', 3), ('u', '<f4', 2), ('m', '<f4', 2), ('c', '<u4')], count=nv, offset=off); off += nv * 32
    ix = np.frombuffer(d, dtype='<u4', count=nf * 3, offset=off); off += nf * 12
    P = np.stack([vb['p'][:, 0], vb['p'][:, 2], vb['p'][:, 1]], 1) / 100.0       # game (x,y,z)*100 = (bx, bz, by)
    me = bpy.data.meshes.new('p%d' % i)
    me.vertices.add(nv); me.vertices.foreach_set('co', P.astype(np.float32).ravel())
    me.loops.add(nf * 3); me.loops.foreach_set('vertex_index', ix.astype(np.int32))
    me.polygons.add(nf); me.polygons.foreach_set('loop_start', (np.arange(nf) * 3).astype(np.int32)); me.polygons.foreach_set('loop_total', np.full(nf, 3, np.int32))
    me.update()
    u0 = me.uv_layers.new(name='UV'); u1 = me.uv_layers.new(name='lm')
    uv = vb['u'][ix].copy(); uv[:, 1] = 1 - uv[:, 1]; lm = vb['m'][ix].copy(); lm[:, 1] = 1 - lm[:, 1]
    u0.data.foreach_set('uv', uv.astype(np.float32).ravel()); u1.data.foreach_set('uv', lm.astype(np.float32).ravel())
    m = bpy.data.materials.new('m%d' % i); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = fac
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    t = nt.nodes.new('ShaderNodeTexImage'); tp = os.path.join(CAP, tex)
    if os.path.exists(tp): t.image = bpy.data.images.load(tp)
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'UV'; nt.links.new(uvn.outputs[0], t.inputs[0])
    lt = nt.nodes.new('ShaderNodeTexImage'); lt.image = img; lt.extension = 'EXTEND'
    ul = nt.nodes.new('ShaderNodeUVMap'); ul.uv_map = 'lm'; nt.links.new(ul.outputs[0], lt.inputs[0])
    if LMONLY: mul.inputs[6].default_value=(1,1,1,1)
    else: nt.links.new(t.outputs['Color'], mul.inputs[6])
    nt.links.new(lt.outputs["Color"], mul.inputs[7])
    nt.links.new(mul.outputs[2], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])
    me.materials.append(m); o = bpy.data.objects.new('p%d' % i, me); col.objects.link(o)
print('PARTS', npart)
pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = 'OPTIX'; pr.get_devices()
for dv in pr.devices: dv.use = (dv.type == 'OPTIX')
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 4; sc.cycles.use_denoising = False
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0
sc.render.resolution_x = 640; sc.render.resolution_y = 480
import math, mathutils
def make_pose_cam():
    x, y, z, yaw, pit, fov = [float(v) for v in open(os.environ.get('POSE', r'C:\Users\HENRIQUE\Tools\captures\pose.txt')).read().split()]
    cp = math.cos(pit); fd = (math.sin(yaw) * cp, math.sin(pit), math.cos(yaw) * cp)     # game dir (x, y-up, z)
    d = mathutils.Vector((fd[0], fd[2], fd[1]))                                          # -> blender (x, y, z-up)
    cd = bpy.data.cameras.new('posecam'); cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(fov); cd.clip_start = 0.05; cd.clip_end = 200
    co = bpy.data.objects.new('pose', cd); bpy.context.scene.collection.objects.link(co)
    co.location = (x / 100.0, z / 100.0, y / 100.0); co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return co
sc.render.resolution_x = 640; sc.render.resolution_y = 360
for n in names:
    if n == 'pose': make_pose_cam()
    if n in ('wallN', 'wallS'):
        cdw = bpy.data.cameras.new(n); cdw.type = 'ORTHO'; cdw.ortho_scale = 21; cdw.clip_start = 0.05; cdw.clip_end = 6.0
        cw = bpy.data.objects.new(n, cdw); sc.collection.objects.link(cw)
        cw.location = (0, 0.5 if n == 'wallN' else -0.5, 2.4); cw.rotation_euler = (1.5708, 0, 0.0 if n == 'wallN' else 3.14159)
        sc.render.resolution_x = 1400; sc.render.resolution_y = 400
    if n == 'floor':
        cdf = bpy.data.cameras.new('floorcam'); cdf.type = 'ORTHO'; cdf.ortho_scale = 20.5; cdf.clip_start = 0.05; cdf.clip_end = 10
        cf = bpy.data.objects.new('floor', cdf); sc.collection.objects.link(cf); cf.location = (0, 0, 2.9); cf.rotation_euler = (0, 0, 0)
        sc.render.resolution_x = 1000; sc.render.resolution_y = 360
    sc.camera = bpy.data.objects[n]; sc.render.filepath = r'C:\Users\HENRIQUE\Tools\re1mod\preview\rms4%s%s_%s.png' % ('lm' if LMONLY else '', os.environ.get('TAG', ''), n)
    bpy.ops.render.render(write_still=True); print('RENDER', n, flush=True)
