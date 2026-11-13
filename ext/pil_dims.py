import bpy, mathutils, numpy as np
for o in sorted([o for o in bpy.data.objects if o.type=='MESH' and ('pil_' in o.name or 'remendo' in o.name or 'pilast' in o.name.lower())],key=lambda o:o.name):
    bb=np.array([o.matrix_world@mathutils.Vector(c) for c in o.bound_box])
    print('P',o.name[:30],'hideR',o.hide_render,'lo',np.round(bb.min(0),3),'hi',np.round(bb.max(0),3),'faces',len(o.data.polygons),[s.material.name[:18] for s in o.material_slots if s.material][:2])
