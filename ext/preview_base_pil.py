import bpy, mathutils, math
pr=bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type='OPTIX'; pr.get_devices()
for d in pr.devices: d.use=(d.type=='OPTIX')
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='GPU'; sc.cycles.samples=64; sc.cycles.use_denoising=True
sc.render.resolution_x=1280; sc.render.resolution_y=720; sc.view_settings.view_transform='Standard'; sc.view_settings.exposure=1.5
cd=bpy.data.cameras.new('c'); cd.sensor_fit='VERTICAL'; cd.angle_y=math.radians(50/1.0); o=bpy.data.objects.new('c',cd); sc.collection.objects.link(o)
o.location=(2.6,0.4,1.4); d=mathutils.Vector((0,math.cos(math.radians(20)),-math.sin(math.radians(20)))); o.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
sc.camera=o; sc.render.filepath=r'C:\Users\HENRIQUE\Tools\re1mod\preview\cycles_basepil.png'; bpy.ops.render.render(write_still=True)
