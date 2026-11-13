import bpy, bmesh, numpy as np
for name in ('remendo_parede_pil_clean_7','remendo_parede_pil_clean_2','remendo_parede_pil_clean_0'):
    o=bpy.data.objects[name]; bm=bmesh.new(); bm.from_mesh(o.data); mw=o.matrix_world
    bm.faces.ensure_lookup_table(); seen=set()
    print('OBJ',name,len(bm.faces),'faces')
    for f in bm.faces:
        if f.index in seen: continue
        st=[f]; comp=[]
        while st:
            x=st.pop()
            if x.index in seen: continue
            seen.add(x.index); comp.append(x)
            for e in x.edges:
                for g in e.link_faces: st.append(g)
        P=np.array([(mw@v.co)[:] for c in comp for v in c.verts])
        print('  PART faces',len(comp),'lo',np.round(P.min(0),3),'hi',np.round(P.max(0),3))
    for f in bm.faces:
        n=(mw.to_3x3()@f.normal).normalized(); P=np.array([(mw@v.co)[:] for v in f.verts])
        print('  F',f.index,'n',np.round(n,2),'lo',np.round(P.min(0),3),'hi',np.round(P.max(0),3))
    bm.free()
p=bpy.data.objects['pil_clean_7']
import mathutils
