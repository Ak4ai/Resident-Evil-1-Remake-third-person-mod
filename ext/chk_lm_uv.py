import bpy, numpy as np
A=0; mn=9; mx=-9; ws=[]
for o in bpy.data.objects:
    if o.type!='MESH' or not o.data.uv_layers.get('lm'): continue
    me=o.data; me.calc_loop_triangles(); lm=me.uv_layers['lm']
    uv=np.array([d.uv[:] for d in lm.data]); 
    if not len(uv): continue
    mn=min(mn,uv.min()); mx=max(mx,uv.max())
    for t in me.loop_triangles:
        a,b,c=[uv[l] for l in t.loops]; A+=abs((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/2
print('CHK area_frac',round(A,3),'min',mn,'max',mx)
