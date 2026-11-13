import bpy, mathutils, math
import os
TAG=os.environ.get('TAG','')
pr=bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type='OPTIX'; pr.get_devices()
for d in pr.devices: d.use=(d.type=='OPTIX')
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='GPU'; sc.cycles.samples=24; sc.cycles.use_denoising=True
sc.render.resolution_x=900; sc.render.resolution_y=600
def shot(name,loc,target):
    cd=bpy.data.cameras.new(name); cd.lens=24; o=bpy.data.objects.new(name,cd); sc.collection.objects.link(o)
    o.location=loc; d=mathutils.Vector(target)-mathutils.Vector(loc); o.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    sc.camera=o; sc.render.filepath=r'C:\Users\HENRIQUE\Tools\re1mod\preview\pier_%s%s.png'%(TAG,name); bpy.ops.render.render(write_still=True)
shot('S',(0.2,-1.6,1.6),(0.9,-3.7,1.6))
shot('N',(-0.2,1.6,1.6),(1.4,3.7,1.6))
