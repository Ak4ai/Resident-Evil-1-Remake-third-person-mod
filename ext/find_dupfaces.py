import bpy, numpy as np, collections
objs=[o for c in ('Fit_Dining','Props') for o in bpy.data.collections[c].all_objects if o and o.type=='MESH' and not o.hide_render]
tot=0; rep=[]
for o in objs:
    me=o.data; mw=np.array(o.matrix_world); co=np.array([v.co[:] for v in me.vertices]); W=(mw[:3,:3]@co.T).T+mw[:3,3]
    me.calc_loop_triangles()
    keys=collections.Counter()
    for t in me.loop_triangles:
        k=tuple(sorted(tuple(np.round(W[v]*500).astype(int)) for v in t.vertices)); keys[k]+=1
    d=sum(c-1 for c in keys.values() if c>1)
    if d: rep.append((d,o.name)); tot+=d
rep.sort(reverse=True); print('DUPTRIS',tot)
for d,n in rep[:25]: print('DF',d,n[:40])
