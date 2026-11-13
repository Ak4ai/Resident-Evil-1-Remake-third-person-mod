# remendo_parede_pil_clean_* (stone base strip beside the pilaster): (1) flatten the chair-rail ledge ("beira", z 1.36..1.50)
# onto the wall plane, so no hole opens; (2) push the edge that touches the pilaster 10 cm into it, closing the corner.
# Vertices only move; the baked 'lm' UV is kept. Saves the .blend (run fix_remendo_tex.py afterwards for the albedo UV).
import bpy, mathutils, numpy as np
pils = [o for o in bpy.data.objects if o.name.startswith('pil_clean_') and o.type == 'MESH']
def bbox(o):
    b = np.array([o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]); return b.min(0), b.max(0)
out = []
for o in [o for o in bpy.data.objects if o.name.startswith('remendo_parede_pil_clean_')]:
    me = o.data; mw = o.matrix_world; mi = mw.inverted()
    W = [mw @ v.co for v in me.vertices]
    s = 1.0 if np.mean([w.y for w in W]) > 0 else -1.0
    ys = [round(abs(w.y), 3) for w in W if w.z > 2.0]
    wall = max(set(ys), key=ys.count)                              # wall plane |y| (most common at the top part)
    x0 = min(w.x for w in W); x1 = max(w.x for w in W)
    lo, hi = bbox(min(pils, key=lambda p: abs((bbox(p)[0][0] + bbox(p)[1][0]) / 2 - (x0 + x1) / 2) + (0 if np.sign(bbox(p)[0][1]) == s else 99)))
    pc = (lo[0] + hi[0]) / 2
    edge = x1 if abs(x1 - pc) < abs(x0 - pc) else x0               # the edge facing the pilaster
    push = 0.10 if pc > edge else -0.10
    nflat = nmove = 0
    for v, w in zip(me.vertices, W):
        w = w.copy()
        if 1.355 < w.z < 1.505 and abs(w.y) < wall - 0.002: w.y = s * wall; nflat += 1
        if abs(w.x - edge) < 1e-3: w.x += push; nmove += 1
        v.co = mi @ w
    me.update(); out.append((o.name[-8:], wall, round(edge, 3), push, nflat, nmove))
for r in out: print('REM', r)
bpy.ops.wm.save_mainfile()
