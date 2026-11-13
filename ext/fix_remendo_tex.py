# remendo_parede_pil_clean_* = the one-sided block beside each pilaster (window/door/painting side, as in the UBC model).
# In UBC that block uses the pilaster stone (s0900_009, object 3_14); ours had the wallpaper (s0900_017). Swap the material
# and give it box-projected UVs at the pilaster's texel density. Geometry and the baked 'lm' UV are untouched. Saves the .blend.
import bpy, mathutils, numpy as np
src = bpy.data.objects['pil_clean_0']
stone = next(sl.material for sl in src.material_slots if sl.material and '009' in sl.material.name)
n = 0
for o in [o for o in bpy.data.objects if o.name.startswith('remendo_parede_pil_clean_')]:
    me = o.data
    me.materials.clear(); me.materials.append(stone)
    for p in me.polygons: p.material_index = 0
    uv = me.uv_layers.get('UVMap') or me.uv_layers[0]
    mw = o.matrix_world; R = mw.to_3x3()
    W = [mw @ v.co for v in me.vertices]; x0 = min(v.x for v in W); x1 = max(v.x for v in W)
    y0 = min(v.y for v in W); y1 = max(v.y for v in W); H = max(v.z for v in W)
    for p in me.polygons:   # UV rects copied from the UBC block (3_14): front u 0.0335..0.1479, side u 0.3118..0.373, v = full height
        nn = (R @ p.normal).normalized()
        for li in p.loop_indices:
            w = W[me.loops[li].vertex_index]; v = w.z / H
            if abs(nn.x) > 0.7: uv.data[li].uv = (0.3118 + (w.y - y0) / max(y1 - y0, 1e-6) * 0.0612, v)
            else: uv.data[li].uv = (0.0335 + (w.x - x0) / max(x1 - x0, 1e-6) * 0.1144, v)
    n += 1
print('REMENDOS', n, 'material', stone.name)
bpy.ops.wm.save_mainfile()
