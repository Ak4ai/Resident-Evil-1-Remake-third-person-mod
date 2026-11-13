import bpy, numpy as np
for o in sorted([o for o in bpy.data.objects if o.name.startswith('remendo_parede')],key=lambda o:o.name):
    mw=o.matrix_world; R=mw.to_3x3(); side=np.sign((mw@o.data.vertices[0].co).y)
    fr=[(R@p.normal).normalized() for p in o.data.polygons if abs((R@p.normal).y)>0.9]
    inward=sum(1 for n in fr if np.sign(n.y)==-side); outward=len(fr)-inward
    ys=sorted(set(round((mw@p.center).y,3) for p in o.data.polygons if abs((R@p.normal).y)>0.9))
    print('R',o.name[-8:],'faces y-facing',len(fr),'into room',inward,'away',outward,'planes',ys[:6])
