import bpy, mathutils, numpy as np, collections
col=bpy.data.collections['Room_W-1F_DiningHall']
F=[]
for o in col.all_objects:
    if o.type!='MESH': continue
    mw=o.matrix_world; R=mw.to_3x3()
    for p in o.data.polygons:
        n=(R@p.normal).normalized(); c=mw@p.center
        vs=[mw@o.data.vertices[i].co for i in p.vertices]
        xs=[v.x for v in vs]; zs=[v.z for v in vs]; ys=[v.y for v in vs]
        F.append((o.name[-6:], o.material_slots[p.material_index].material.name[:12] if o.material_slots else '', n.x,n.y,n.z,c.x,c.y,c.z,min(xs),max(xs),min(zs),max(zs),min(ys),max(ys)))
F=np.array(F,dtype=object)
# faces facing the room on the south wall of UBC (y<0 side) near x in [-22.6,-20.4], spanning z=2
for side in (1,-1):
    print('SIDE',side)
    rows=[]
    for f in F:
        nx,ny,nz=f[2],f[3],f[4]; cx,cy,cz=f[5],f[6],f[7]
        if np.sign(cy)!=side or not(-24.5<cx<-18.5) or not(f[10]<1.8<f[11]): continue
        if abs(ny)>0.9: rows.append(('Yface',round(cy,3),round(f[8],3),round(f[9],3),f[1],f[0]))
        elif abs(nx)>0.9: rows.append(('Xface',round(cx,3),round(f[12],3),round(f[13],3),f[1],f[0]))
    for r in sorted(set(rows),key=lambda r:(r[0],r[2]))[:60]: print(r)
