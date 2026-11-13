import bpy, mathutils, numpy as np
objs=[o for c in ('Fit_Dining','Props') for o in bpy.data.collections[c].all_objects if o and o.type=='MESH' and not o.hide_render]
for y0 in (3.80,3.84):
  for (x,z) in ((-5.25,1.5),(0.08,1.5),(5.4,2.0)):
    o0=mathutils.Vector((x,y0,z)); d=mathutils.Vector((0,1,0)); best=None
    for o in objs:
        mi=o.matrix_world.inverted(); r=o.ray_cast(mi@o0,(mi.to_3x3()@d).normalized(),distance=30)
        if r[0]:
            hw=o.matrix_world@r[1]; dist=(hw-o0).length
            if best is None or dist<best[0]:
                m=o.material_slots[o.data.polygons[r[3]].material_index].material if o.material_slots else None
                best=(round(dist,3),o.name[:30],m.name if m else None)
    print('BEHIND y0=%.2f x=%.2f z=%.1f'%(y0,x,z),best)
# texture alpha of the pane material
m=bpy.data.materials.get('s0900_052_bm_Alpha')
imgs=[n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image] if m else []
for im in imgs: print('IMG',im.name,im.size[:],im.channels,im.alpha_mode,im.filepath[-60:])
print('BLEND', m.blend_method if m else None, [ (n.type) for n in m.node_tree.nodes][:12] if m else None)
