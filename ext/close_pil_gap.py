# Moves the south pilasters (back face at y=-3.749, wall at about -3.756) onto the wall, closing the 6-8 mm gap. Saves the file.
import bpy, mathutils, numpy as np
moved=[]
for o in bpy.data.objects:
    if not o.name.startswith('pil_clean_') or o.type!='MESH': continue
    bb=np.array([o.matrix_world@mathutils.Vector(c) for c in o.bound_box])
    if bb[:,1].mean()<-2.5 and abs(bb[:,1].min()+3.749)<0.002:
        o.location.y-=0.008; moved.append(o.name)
print('MOVED',moved)
bpy.ops.wm.save_mainfile()
