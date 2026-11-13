import bpy, bmesh, numpy as np, mathutils
o=bpy.data.objects['ch_p0']; mw=o.matrix_world
bm=bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
mats=[s.material.name if s.material else None for s in o.material_slots]
print('MATS',mats, 'loc',tuple(round(v,3) for v in mw.translation))
seen=set(); comps=[]
for f in bm.faces:
    if f.index in seen: continue
    st=[f]; comp=[]
    while st:
        x=st.pop()
        if x.index in seen: continue
        seen.add(x.index); comp.append(x)
        for e in x.edges:
            for g in e.link_faces:
                if g.material_index==x.material_index: st.append(g)
    P=np.array([(mw@v.co)[:] for c in comp for v in c.verts])
    bnd=sum(1 for c in comp for e in c.edges if len(e.link_faces)==1)
    comps.append((len(comp),mats[comp[0].material_index],np.round(P.min(0),3),np.round(P.max(0),3),bnd))
for c in sorted(comps,key=lambda c:-c[0])[:25]: print('C',c)
