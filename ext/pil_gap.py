import bpy, mathutils, numpy as np
from mathutils.bvhtree import BVHTree
dg=bpy.context.evaluated_depsgraph_get()
objs=[o for c in ('Fit_Dining','Props') for o in bpy.data.collections[c].all_objects if o and o.type=='MESH' and not o.hide_render]
pils=[o for o in objs if o.name.startswith('pil_') or 'pil_S' in o.name]
others=[o for o in objs if o not in pils]
# BVH of everything except pilasters
vs=[];fs=[];off=0
for o in others:
    me=o.evaluated_get(dg).to_mesh(); mw=o.matrix_world
    vs+= [mw@v.co for v in me.vertices]; fs+=[[off+i for i in p.vertices] for p in me.polygons]; off+=len(me.vertices); o.evaluated_get(dg).to_mesh_clear()
T=BVHTree.FromPolygons(vs,fs)
for o in pils:
    bb=np.array([o.matrix_world@mathutils.Vector(c) for c in o.bound_box]); lo,hi=bb.min(0),bb.max(0); cen=(lo+hi)/2
    # wall side = towards larger |y| (side walls) or larger |x|
    ax=1 if abs(cen[1])>2.5 else 0; sgn=np.sign(cen[ax])
    res=[]
    for z in np.linspace(lo[2]+0.2,hi[2]-0.2,5):
        for side in (0,1):   # sample along both lateral edges of the pilaster back
            p=cen.copy(); p[2]=z
            other=1-ax; p[other]=lo[other]+0.01 if side==0 else hi[other]-0.01
            p[ax]=hi[ax] if sgn>0 else lo[ax]
            d=mathutils.Vector((0,0,0)); d[ax]=sgn
            h=T.ray_cast(mathutils.Vector(p)-d*0.05,d,2.0)
            res.append(round((h[3]-0.05),3) if h[0] else None)
    print('PIL',o.name[:24],'axis','xy'[ax],'back',round(float(hi[ax] if sgn>0 else lo[ax]),3),'gap m',res)
