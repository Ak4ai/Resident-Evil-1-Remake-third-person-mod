import bpy, mathutils, math
sc=bpy.context.scene
col=bpy.data.collections.get('Room_W-1F_DiningHall')
keep=set(o.name for o in col.all_objects) if col else set()
for o in bpy.data.objects:
    if o.type=='MESH': o.hide_render = o.name not in keep
sc.render.engine='BLENDER_WORKBENCH'; sh=sc.display.shading; sh.light='STUDIO'; sh.color_type='TEXTURE'; sh.show_cavity=True
sc.render.resolution_x=1400; sc.render.resolution_y=500
def cam(name,loc,rot,ortho=None,lens=None):
    cd=bpy.data.cameras.new(name)
    if ortho: cd.type='ORTHO'; cd.ortho_scale=ortho
    if lens: cd.lens=lens
    cd.clip_start=0.05; cd.clip_end=40
    o=bpy.data.objects.new(name,cd); sc.collection.objects.link(o); o.location=loc; o.rotation_euler=rot; return o
# find wall extents
import numpy as np
bb=np.array([o.matrix_world@mathutils.Vector(c) for n in keep for o in [bpy.data.objects[n]] if o.type=='MESH' for c in o.bound_box])
print('ROOM',np.round(bb.min(0),2),np.round(bb.max(0),2))
cx=-21.5
for nm,loc,rot,o_,l_ in (('elevN',(cx,0,2.4),(math.pi/2,0,0),24,None),('elevS',(cx,0,2.4),(math.pi/2,0,math.pi),24,None)):
    sc.camera=cam(nm,loc,rot,o_,l_); sc.render.filepath=r'C:\Users\HENRIQUE\Tools\re1mod\preview\ubc_%s.png'%nm; bpy.ops.render.render(write_still=True)
print('DONE')
