import bpy, mathutils
o=bpy.data.objects['Combined Mesh (root: scene) 3_14']; me=o.data; mw=o.matrix_world; R=mw.to_3x3()
uv=me.uv_layers.active
for p in me.polygons:
    n=(R@p.normal).normalized(); c=mw@p.center
    if -23.0<c.x<-22.3 and c.y>6.0 and (abs(n.y)>0.9 or abs(n.x)>0.9):
        pts=[(tuple(round(v,3) for v in (mw@me.vertices[me.loops[l].vertex_index].co)), tuple(round(v,4) for v in uv.data[l].uv)) for l in p.loop_indices]
        print('F', 'n', tuple(round(v,2) for v in n), pts)
