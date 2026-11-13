import bpy, math, mathutils
sc=bpy.context.scene
print('RES',sc.render.resolution_x,sc.render.resolution_y)
for o in sorted([o for o in bpy.data.objects if o.type=='CAMERA' and o.name.startswith('cam')],key=lambda o:o.name):
    d=o.matrix_world.to_quaternion()@mathutils.Vector((0,0,-1)); c=o.data
    print('CAM',o.name,tuple(round(v,3) for v in o.matrix_world.translation),'dir',tuple(round(v,3) for v in d),'ay',round(math.degrees(c.angle_y),2),'ax',round(math.degrees(c.angle_x),2),c.sensor_fit,round(c.shift_x,3),round(c.shift_y,3))
