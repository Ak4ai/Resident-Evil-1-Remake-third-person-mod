import bpy, bmesh, numpy as np, mathutils, math
o=bpy.data.objects['ch_p0']; mw=o.matrix_world
bm=bmesh.new(); bm.from_mesh(o.data)
fab=[f for f in bm.faces if o.material_slots[f.material_index].material.name=='yg_fabric_01']
P=np.array([(mw@v.co)[:] for f in fab for v in f.verts]); lo,hi=P.min(0),P.max(0)
print('FAB faces',len(fab),'lo',np.round(lo,3),'hi',np.round(hi,3))
bes=set(e for f in fab for e in f.edges if sum(1 for g in e.link_faces if g in fab)==1)
inner=[]
for e in bes:
    a=mw@e.verts[0].co; b=mw@e.verts[1].co; m=(a+b)/2
    # back cushion only (vertical), interior = far from its outline
    if m.z>0.55 and m.y<-1.30:
        inner.append((round(m.x,3),round(m.y,3),round(m.z,3),round((a-b).length,3)))
print('BOUNDARY back-cushion edges',len(inner))
for r in sorted(inner): print('E',r)
# render close-up
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'; sc.display.shading.color_type='TEXTURE'; sc.display.shading.light='FLAT'
sc.render.resolution_x=900; sc.render.resolution_y=900
cd=bpy.data.cameras.new('c'); cd.lens=50; c=bpy.data.objects.new('c',cd); sc.collection.objects.link(c)
c.location=(-4.7,-2.4,0.8); c.rotation_euler=mathutils.Vector((0,1,0)).to_track_quat('-Z','Z').to_euler()
sc.camera=c; sc.render.filepath=r'C:\Users\HENRIQUE\Tools\re1mod\preview\chair_back.png'; sc.render.image_settings.file_format='PNG'; bpy.ops.render.render(write_still=True)
