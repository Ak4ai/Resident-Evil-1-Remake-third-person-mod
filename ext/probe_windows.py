import bpy, mathutils, numpy as np
from mathutils.bvhtree import BVHTree
dg=bpy.context.evaluated_depsgraph_get()
objs=[o for c in ('Fit_Dining','Props') for o in bpy.data.collections[c].all_objects if o and o.type=='MESH' and not o.hide_render]
for x in (-5.25,0.08,5.4):
  for z in (1.2,1.8,2.3):
    for dx in (-0.35,0.0,0.35):
        o0=mathutils.Vector((x+dx,0.0,z)); d=mathutils.Vector((0,1,0)); best=None
        for o in objs:
            mi=o.matrix_world.inverted(); r=o.ray_cast(mi@o0, (mi.to_3x3()@d).normalized(), distance=10)
            if r[0]:
                hw=o.matrix_world@r[1]; dist=(hw-o0).length
                if best is None or dist<best[0]:
                    slot=o.material_slots[o.data.polygons[r[3]].material_index].material if o.material_slots else None
                    best=(dist,o.name,slot.name if slot else None,r[3],tuple(round(v,3) for v in hw))
        print('HIT x=%.2f z=%.1f dx=%.2f'%(x,z,dx),best)
