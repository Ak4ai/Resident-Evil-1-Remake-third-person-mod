import bpy, numpy as np
T=[];W=[]
for o in bpy.data.objects:
    if o.type!='MESH' or not o.data.uv_layers.get('lm'): continue
    me=o.data; me.calc_loop_triangles(); uv=np.array([d.uv[:] for d in me.uv_layers['lm'].data])
    co=np.array([v.co[:] for v in me.vertices]); mw=np.array(o.matrix_world); Wd=(mw[:3,:3]@co.T).T+mw[:3,3]
    for t in me.loop_triangles:
        T.append(uv[list(t.loops)]); a,b,c=[Wd[v] for v in t.vertices]; W.append(np.linalg.norm(np.cross(b-a,c-a))/2)
np.savez(r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\uvdump.npz',T=np.array(T,np.float32),W=np.array(W,np.float32))
