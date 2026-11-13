# Plan-view profile of the side walls from the game depth maps vs the model: median |y| per 2 cm x-bin at mid height.
import bpy, bmesh, numpy as np, mathutils, sys
from mathutils.bvhtree import BVHTree
sc=bpy.context.scene; dg=bpy.context.evaluated_depsgraph_get()
bm=bmesh.new()
for o in [o for o in bpy.context.view_layer.objects if o.visible_get() and o.type=='MESH' and not o.hide_render]:
    ev=o.evaluated_get(dg); me=ev.to_mesh(); t=bmesh.new(); t.from_mesh(me); t.transform(o.matrix_world); vm={}
    for v in t.verts: vm[v.index]=bm.verts.new(v.co)
    for f in t.faces:
        try: bm.faces.new([vm[v.index] for v in f.verts])
        except ValueError: pass
    t.free(); ev.to_mesh_clear()
tree=BVHTree.FromBMesh(bm); bm.free()
DEP=dict(np.load(r'C:\Users\HENRIQUE\Tools\re1mod\ext\bg\depth.npz'))
G_pts=[]; M_pts=[]
for i in (9,10,33,35,26,24,11,3,5,4):
    n=f'cam{i:02d}'
    if n not in bpy.data.objects or f'c{i}' not in DEP: continue
    cam=bpy.data.objects[n]; G=DEP[f'c{i}']
    fr=[cam.matrix_world@c for c in cam.data.view_frame(scene=sc)]; tr,br,bl,tl=fr; org=cam.matrix_world.translation
    fwd=(cam.matrix_world.to_3x3()@mathutils.Vector((0,0,-1))).normalized()
    for j in range(12,348,1):
        for k in range(0,480,1):
            g=G[j,k]
            if g<=0.05: continue
            py=j*4+2-48; px=(1-(k*4+2)/1920)*1728
            if not (0<=py<1344): continue
            p=bl+(br-bl)*(px/1728)+(tl-bl)*(1-py/1344); d=(p-org).normalized()
            gp=org+d*(g/d.dot(fwd))
            if 1.2<gp.z<1.9 and 2.9<abs(gp.y)<4.0 and abs(gp.x)<9:
                G_pts.append((gp.x,gp.y))
                loc,nrm,idx,dist=tree.ray_cast(org+d*0.3,d)
                if loc is not None: M_pts.append((loc.x,loc.y))
G_pts=np.array(G_pts); M_pts=np.array(M_pts)
np.savez(r'C:\Users\HENRIQUE\Tools\re1mod\preview\wall_profile.npz',G=G_pts,M=M_pts)
print('PTS',len(G_pts),len(M_pts))
