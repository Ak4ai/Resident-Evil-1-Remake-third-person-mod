import bpy, mathutils, numpy as np
print('FILE',bpy.data.filepath)
objs=[o for o in bpy.data.objects if o.type=='MESH']
print('NOBJ',len(objs))
for o in objs:
    mats=[s.material.name for s in o.material_slots if s.material]
    if any('s0900_017' in m or 's0900_009' in m or 's0900_001' in m for m in mats):
        b=np.array([o.matrix_world@mathutils.Vector(c) for c in o.bound_box])
        print('O',o.name[:40],[m[:16] for m in mats][:5],np.round(b.min(0),2),np.round(b.max(0),2),len(o.data.polygons),'hide',o.hide_render, [c.name for c in o.users_collection][:2])
