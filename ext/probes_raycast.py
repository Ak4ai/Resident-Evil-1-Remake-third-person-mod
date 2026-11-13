# Light-probe grid for the characters (step 1 of 2, inside Blender on r105_lm.blend):
# from every probe, cast R rays over the sphere against the exported room geometry and record, per ray, the hit
# triangle's lightmap UV and albedo texture key. ext/probes_build.py then turns that into per-layer ambient SH.
import bpy, numpy as np, mathutils, re, pickle
from mathutils.bvhtree import BVHTree
R = 160
X = np.arange(-9.5, 9.51, 1.0); Y = np.arange(-3.5, 3.51, 1.0); Z = np.array([0.3, 0.9, 1.5, 2.1, 2.7])
dg = bpy.context.evaluated_depsgraph_get()
def base_image(m):
    if not m or not m.use_nodes: return None
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
def base_color(m):
    if m and m.use_nodes:
        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if b: return tuple(round(c, 3) for c in b.inputs['Base Color'].default_value[:3])
    return (0.5, 0.5, 0.5)
V = []; F = []; LMUV = []; KEY = []; keys = {}
objs = [o for c in ('Fit_Dining', 'Props') for o in bpy.data.collections[c].all_objects if o and o.type == 'MESH' and not o.hide_render]
for o in objs:
    ev = o.evaluated_get(dg); me = ev.to_mesh(); me.calc_loop_triangles(); mw = o.matrix_world
    base = len(V); V += [mw @ v.co for v in me.vertices]
    lm = me.uv_layers.get('lm')
    for t in me.loop_triangles:
        F.append([base + i for i in t.vertices])
        LMUV.append([lm.data[l].uv[:] for l in t.loops] if lm else [(0, 0)] * 3)
        m = o.material_slots[t.material_index].material if t.material_index < len(o.material_slots) else None
        img = base_image(m); k = ('img', img.name) if img else ('col', base_color(m))
        KEY.append(keys.setdefault(k, len(keys)))
    ev.to_mesh_clear()
tree = BVHTree.FromPolygons(V, F)
F = np.array(F); Vn = np.array([v[:] for v in V]); LMUV = np.array(LMUV, np.float32); KEY = np.array(KEY, np.int32)
i = np.arange(R) + 0.5; phi = np.arccos(1 - 2 * i / R); th = np.pi * (1 + 5 ** 0.5) * i
D = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)   # blender axes
P = np.array([(x, y, z) for x in X for y in Y for z in Z])
hit_lm = np.zeros((len(P), R, 2), np.float32); hit_key = np.full((len(P), R), -1, np.int32); hit_d = np.zeros((len(P), R), np.float32)
for pi, p in enumerate(P):
    o = mathutils.Vector(p)
    for ri, d in enumerate(D):
        loc, nrm, idx, dist = tree.ray_cast(o, mathutils.Vector(d), 40.0)
        if idx is None: continue
        a, b, c = Vn[F[idx]]; q = np.array(loc[:])
        v0, v1, v2 = b - a, c - a, q - a
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1; den = d00 * d11 - d01 * d01
        if abs(den) < 1e-14: continue
        w1 = (d11 * d20 - d01 * d21) / den; w2 = (d00 * d21 - d01 * d20) / den; w0 = 1 - w1 - w2
        hit_lm[pi, ri] = w0 * LMUV[idx, 0] + w1 * LMUV[idx, 1] + w2 * LMUV[idx, 2]
        hit_key[pi, ri] = KEY[idx]; hit_d[pi, ri] = dist
inv = {v: k for k, v in keys.items()}
np.savez(r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\probes_rays.npz', P=P, D=D, X=X, Y=Y, Z=Z, lm=hit_lm, key=hit_key, dist=hit_d)
pickle.dump(inv, open(r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\probes_keys.pkl', 'wb'))
print('PROBES', len(P), 'rays', R, 'hit frac', float((hit_key >= 0).mean()))
