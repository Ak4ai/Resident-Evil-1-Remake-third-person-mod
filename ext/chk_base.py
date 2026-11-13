import bpy, mathutils, numpy as np
for n in ('pil_clean_7','remendo_parede_pil_clean_7','base_pil_7_m','pil_clean_4','base_pil_4_a','base_pil_4_b'):
    o=bpy.data.objects.get(n)
    b=np.array([o.matrix_world@mathutils.Vector(c) for c in o.bound_box])
    print('B',n,np.round(b.min(0),3),np.round(b.max(0),3),[c.name for c in o.users_collection],o.hide_render,len(o.data.uv_layers), [u.name for u in o.data.uv_layers])
