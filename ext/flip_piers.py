import bpy
n=0
for o in bpy.data.objects:
    if o.name.startswith('pier_'):
        o.data.flip_normals(); o.data.update(); n+=1
        c=o.matrix_world@o.data.polygons[0].center; nm=o.data.polygons[0].normal
print('FLIPPED',n,'front0 normal',tuple(round(v,2) for v in nm),'y',round(c.y,2))
bpy.ops.wm.save_mainfile()
