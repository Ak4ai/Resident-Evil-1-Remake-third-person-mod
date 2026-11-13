import bpy, numpy as np
best=None
for o in bpy.data.objects:
    if o.type!='MESH' or not o.data.uv_layers.get('lm') or o.hide_render: continue
    me=o.data; mw=np.array(o.matrix_world); lm=me.uv_layers['lm']; A=0; us=[]
    for p in me.polygons:
        n=mw[:3,:3]@np.array(p.normal); c=mw[:3,:3]@np.array(p.center)+mw[:3,3]
        if n[2]>0.9*np.linalg.norm(n) and abs(c[2])<0.15:
            A+=p.area
            us+= [lm.data[l].uv[:] for l in p.loop_indices]
    if A>5 and (best is None or A>best[0]): best=(A,o.name,np.array(us).min(0),np.array(us).max(0))
print('FLOOR',best[1][:40],round(best[0],1),best[2],best[3])
