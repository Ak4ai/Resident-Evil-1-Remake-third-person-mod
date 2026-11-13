import bpy, mathutils, numpy as np
for o in bpy.data.objects:
    if o.type!='MESH' or o.hide_render: continue
    n=o.name.lower(); mats=[s.material.name for s in o.material_slots if s.material]
    if any(k in n for k in ('arch','door','porta','jan','win','arco','dz','glass','vidro')) or any(any(k in m.lower() for k in ('door','win','glass','arch')) for m in mats):
        bb=np.array([o.matrix_world@mathutils.Vector(c) for c in o.bound_box])
        print('OBJ',o.name[:32],'mats',[m[:22] for m in mats][:3],'lo',np.round(bb.min(0),2),'hi',np.round(bb.max(0),2),len(o.data.polygons))
