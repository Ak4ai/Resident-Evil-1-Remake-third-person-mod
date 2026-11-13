import bpy, mathutils, numpy as np
objs=[o for c in ('Fit_Dining','Props') for o in bpy.data.collections[c].all_objects if o and o.type=='MESH' and not o.hide_render]
B=[]
for o in objs:
    bb=np.array([o.matrix_world@mathutils.Vector(c) for c in o.bound_box]); B.append((bb.min(0),bb.max(0)))
pairs=[]
for i in range(len(objs)):
    for j in range(i+1,len(objs)):
        a0,a1=B[i]; b0,b1=B[j]
        if np.abs(a0-b0).max()<0.02 and np.abs(a1-b1).max()<0.02: pairs.append((objs[i].name,objs[j].name,len(objs[i].data.polygons),len(objs[j].data.polygons)))
print('DUPS',len(pairs))
for p in pairs[:40]: print('DUP',p[0][:35],'|',p[1][:35],p[2],p[3])
# chairs: material/texture names containing isu
for o in objs:
    mats=[s.material.name for s in o.material_slots if s.material]
    if any('isu' in m.lower() or 'chair' in m.lower() for m in mats) or 'isu' in o.name.lower() or 'chair' in o.name.lower():
        print('CHAIR',o.name[:35],len(o.data.polygons),[m[:20] for m in mats][:3])
