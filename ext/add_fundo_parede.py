# Closes the see-through seams between pilasters and the side walls: a wall-coloured backing behind the north wall
# (with holes at the 3 windows, so the landscape still shows) and behind the south wall. Saves the .blend.
import bpy, numpy as np
COL = (0.235, 0.215, 0.19)          # wall tone (display), lit by the emissive path in the mod
img = bpy.data.images.get('paisagem_fundo_parede.png') or bpy.data.images.new('paisagem_fundo_parede.png', 4, 4)
img.pixels.foreach_set(np.tile(np.array(COL + (1.0,), np.float32), 16))
img.filepath_raw = r'C:\Users\HENRIQUE\Tools\captures\r105m_paisagem_fundo_parede.png'; img.file_format = 'PNG'; img.save()
for n in ('fundo_parede_N', 'fundo_parede_S'):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)
def make(name, quads, y):
    vs, fs = [], []
    for (x0, x1, z0, z1) in quads:
        k = len(vs); vs += [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
        fs.append((k, k + 3, k + 2, k + 1) if y > 0 else (k, k + 1, k + 2, k + 3))   # face the room
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); uv = me.uv_layers.new(name='UVMap'); me.uv_layers.new(name='lm')
    for d in uv.data: d.uv = (0.5, 0.5)
    m = bpy.data.materials.get('paisagem_fundo_parede') or bpy.data.materials.new('paisagem_fundo_parede'); m.use_nodes = True
    nt = m.node_tree; bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    if not any(n.type == 'TEX_IMAGE' for n in nt.nodes):
        tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img; nt.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
    me.materials.append(m); o = bpy.data.objects.new(name, me); bpy.data.collections['Props'].objects.link(o)
X0, X1, Z0, Z1 = -9.7, 9.7, -0.05, 4.3
WIN = [(-5.25 - 0.82, -5.25 + 0.82), (0.08 - 0.82, 0.08 + 0.82), (5.4 - 0.82, 5.4 + 0.82)]; WZ0, WZ1 = 0.80, 2.95
q = [(X0, X1, Z0, WZ0), (X0, X1, WZ1, Z1)]
xs = [X0] + [v for w in WIN for v in w] + [X1]
for i in range(0, len(xs), 2): q.append((xs[i], xs[i + 1], WZ0, WZ1))
make('fundo_parede_N', q, 3.87)
make('fundo_parede_S', [(X0, X1, Z0, Z1)], -3.87)
bpy.ops.wm.save_mainfile()
print('FUNDO ok')
