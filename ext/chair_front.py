import bpy, mathutils, math
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'; sc.display.shading.color_type='TEXTURE'; sc.display.shading.light='STUDIO'
sc.render.resolution_x=900; sc.render.resolution_y=900
for nm,loc in (('front',(-4.7,-0.2,1.5)),('back',(-4.7,-2.4,1.2))):
    cd=bpy.data.cameras.new(nm); cd.lens=40; c=bpy.data.objects.new(nm,cd); sc.collection.objects.link(c)
    c.location=loc; d=mathutils.Vector((-4.7,-1.36,0.8))-mathutils.Vector(loc); c.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    sc.camera=c; sc.render.filepath=r'C:\Users\HENRIQUE\Tools\re1mod\preview\chair_bl_%s.png'%nm; sc.render.image_settings.file_format='PNG'; bpy.ops.render.render(write_still=True)
