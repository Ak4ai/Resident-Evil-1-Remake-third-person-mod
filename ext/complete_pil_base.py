# The wider "base" pilaster behind each wall pilaster (remendo_parede_pil_clean_*) existed only on ONE side of each pilaster.
# This mirrors it to the missing side (and copies a neighbour's for pilasters that had none), keeping the 'lm' UV so the copy
# reuses the baked light of its source. Objects: base_pil_<i>_<L|R>. Saves the .blend.
import bpy, bmesh, mathutils, numpy as np
pils = {int(o.name.split('_')[-1]): o for o in bpy.data.objects if o.name.startswith('pil_clean_') and o.type == 'MESH'}
rem = {int(o.name.split('_')[-1]): o for o in bpy.data.objects if o.name.startswith('remendo_parede_pil_clean_') and o.type == 'MESH'}
for o in [o for o in bpy.data.objects if o.name.startswith('base_pil_')]: bpy.data.objects.remove(o, do_unlink=True)
def bbox(o):
    b = np.array([o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]); return b.min(0), b.max(0)
def cx(o): lo, hi = bbox(o); return (lo[0] + hi[0]) / 2
def copy_world(src, name, fx):
    me = src.data.copy(); bm = bmesh.new(); bm.from_mesh(me); mw = src.matrix_world
    mirror = False
    for v in bm.verts:
        w = mw @ v.co; nx, mir = fx(w.x); v.co = mathutils.Vector((nx, w.y, w.z)); mirror = mir
    if mirror: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free(); me.update()
    o = bpy.data.objects.new(name, me)
    for c in src.users_collection: c.objects.link(o)
    return o
made = []
for i, p in pils.items():
    c = cx(p); lo, hi = bbox(p); wall = np.sign((lo[1] + hi[1]) / 2)
    r = rem.get(i)
    if r is None:   # borrow from the nearest pilaster on the same wall that has one
        cand = [(abs(cx(pils[j]) - c), j) for j in rem if np.sign(bbox(pils[j])[0][1] + bbox(pils[j])[1][1]) == wall]
        j = min(cand)[1]; r = rem[j]; d = c - cx(pils[j])
        o1 = copy_world(r, f'base_pil_{i}_a', lambda x, d=d: (x + d, False)); made.append(o1.name)
        side = np.sign(cx(r) + d - c)
        o2 = copy_world(r, f'base_pil_{i}_b', lambda x, d=d, c=c: (2 * c - (x + d), True)); made.append(o2.name)
    else:
        o = copy_world(r, f'base_pil_{i}_m', lambda x, c=c: (2 * c - x, True)); made.append(o.name)
print('BASES', len(made), made)
bpy.ops.wm.save_mainfile()
