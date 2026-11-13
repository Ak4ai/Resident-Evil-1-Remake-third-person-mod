import bpy, bmesh
n=0
for o in bpy.data.objects:
    if o.name.startswith('ch_') and o.type=='MESH':
        me=o.data; bm=bmesh.new(); bm.from_mesh(me)
        fi=[i for i,s in enumerate(o.material_slots) if s.material and 'fabric' in s.material.name]
        for v in set(v for f in bm.faces if f.material_index in fi for v in f.verts): v.co+=v.normal*0.004
        bm.to_mesh(me); bm.free(); me.update(); n+=1
print('PUSHED',n); bpy.ops.wm.save_mainfile()
