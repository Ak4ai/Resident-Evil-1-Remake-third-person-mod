import bpy, bmesh, numpy as np
for name in ('pil_zp','pil_zn'):
    o=bpy.data.objects[name]; bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    seen=set(); mw=o.matrix_world
    for v in bm.verts:
        if v.index in seen: continue
        stack=[v]; comp=[]
        while stack:
            x=stack.pop()
            if x.index in seen: continue
            seen.add(x.index); comp.append(x)
            for e in x.link_edges: stack.append(e.other_vert(x))
        P=np.array([(mw@x.co)[:] for x in comp]); print('PART',name,np.round(P.min(0),3),np.round(P.max(0),3))
