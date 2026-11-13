# Wider "base" pier behind every wall pilaster, on BOTH sides (as in the original game backgrounds): plain stone box
# from the wall to |y|=3.605, pilaster width + 0.26 m each side, z 0..3.70. Replaces the one-sided remendo_parede_* strips
# (hidden). Each pier gets its own 128x128 free block of the lightmap atlas (UV 'lm'), to be baked by bake_lm_layers.py
# with LM_ONLY=pier_. Saves the .blend.
import bpy, mathutils, numpy as np
REG = [(64, 320), (64, 512), (64, 704), (320, 320), (320, 512), (320, 704), (704, 64), (704, 288), (704, 544), (896, 64), (896, 288), (896, 544)]
SZ = 128; PAD = 4; A = 4096.0
EXT, FRONT, BACK, ZT = 0.26, 3.605, 3.80, 3.70
for o in [o for o in bpy.data.objects if o.name.startswith('pier_')]: bpy.data.objects.remove(o, do_unlink=True)
for o in bpy.data.objects:
    if o.name.startswith('remendo_parede_pil_clean_'): o.hide_render = True; o.hide_viewport = True
pils = sorted([o for o in bpy.data.objects if o.name.startswith('pil_clean_') and o.type == 'MESH'], key=lambda o: int(o.name.split('_')[-1]))
def bbox(o):
    b = np.array([o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]); return b.min(0), b.max(0)
def density(o, mname):
    me = o.data; uv = me.uv_layers['UVMap'] if 'UVMap' in me.uv_layers else me.uv_layers[0]; mw = o.matrix_world; r = []
    for p in me.polygons:
        m = o.material_slots[p.material_index].material
        if not m or mname not in m.name or p.area < 0.05: continue
        L = list(p.loop_indices)
        if len(L) < 3: continue
        u = [mathutils.Vector(uv.data[l].uv) for l in L[:3]]; w = [mw @ me.vertices[me.loops[l].vertex_index].co for l in L[:3]]
        ua = abs((u[1] - u[0]).cross(u[2] - u[0])) / 2; wa = ((w[1] - w[0]).cross(w[2] - w[0])).length / 2
        if wa > 1e-6: r.append((ua / wa) ** 0.5)
    return float(np.median(r)) if r else 0.5
made = []
for k, p in enumerate(pils):
    lo, hi = bbox(p); s = 1.0 if (lo[1] + hi[1]) > 0 else -1.0
    x0, x1 = lo[0] - EXT, hi[0] + EXT; yf, yb = s * FRONT, s * BACK
    mat = next((sl.material for sl in p.material_slots if sl.material and '009' in sl.material.name), p.material_slots[0].material)
    dens = density(p, '009')
    # quads (counter-clockwise seen from the room)
    if s > 0:
        quads = {'front': [(x0, yf, 0), (x0, yf, ZT), (x1, yf, ZT), (x1, yf, 0)],
                 'left': [(x0, yb, 0), (x0, yb, ZT), (x0, yf, ZT), (x0, yf, 0)],
                 'right': [(x1, yf, 0), (x1, yf, ZT), (x1, yb, ZT), (x1, yb, 0)],
                 'top': [(x0, yf, ZT), (x0, yb, ZT), (x1, yb, ZT), (x1, yf, ZT)]}
    else:
        quads = {'front': [(x1, yf, 0), (x1, yf, ZT), (x0, yf, ZT), (x0, yf, 0)],
                 'left': [(x1, yb, 0), (x1, yb, ZT), (x1, yf, ZT), (x1, yf, 0)],
                 'right': [(x0, yf, 0), (x0, yf, ZT), (x0, yb, ZT), (x0, yb, 0)],
                 'top': [(x1, yf, ZT), (x1, yb, ZT), (x0, yb, ZT), (x0, yf, ZT)]}
    verts = []; faces = []
    for q in quads.values(): faces.append(tuple(range(len(verts), len(verts) + 4))); verts += q
    me = bpy.data.meshes.new(f'pier_{k}'); me.from_pydata(verts, [], faces); me.update()
    uv = me.uv_layers.new(name='UVMap'); lm = me.uv_layers.new(name='lm')
    # lightmap layout inside the 128x128 block: front | left | right | top (texels), scale to fit the height
    r0, c0 = REG[k]; W = x1 - x0; D = abs(yb - yf); sc = (SZ - 2 * PAD) / ZT
    boxes = {'front': (PAD, PAD, W, ZT), 'left': (PAD + W * sc + 4, PAD, D, ZT), 'right': (PAD + (W + D) * sc + 8, PAD, D, ZT),
             'top': (PAD + (W + 2 * D) * sc + 12, PAD, D, W)}   # top drawn rotated (depth along u)
    for fi, (name, q) in enumerate(quads.items()):
        poly = me.polygons[fi]; bx, by, bw, bh = boxes[name]
        for li, corner in zip(poly.loop_indices, [(0, 0), (0, 1), (1, 1), (1, 0)]):
            P = verts[me.loops[li].vertex_index]
            if name == 'front': uv.data[li].uv = (P[0] * dens, P[2] * dens)
            elif name == 'top': uv.data[li].uv = (P[0] * dens, P[1] * dens)
            else: uv.data[li].uv = (P[1] * dens, P[2] * dens)
            if name == 'top': cu, cv = corner[1], corner[0]
            else: cu, cv = corner
            lm.data[li].uv = ((c0 + bx + cu * bw * sc) / A, (r0 + by + cv * bh * sc) / A)
    me.materials.append(mat)
    o = bpy.data.objects.new(f'pier_{k}', me); bpy.data.collections['Fit_Dining'].objects.link(o); made.append(o.name)
print('PIERS', len(made), 'uv density', round(dens, 3))
bpy.ops.wm.save_mainfile()
