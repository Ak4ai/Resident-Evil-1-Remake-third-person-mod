# Adds the night landscape behind the north windows: hides the black backing plane (fundo_armarios_zp) and creates a
# textured plane 'paisagem_janelas' 3.7 m behind the wall (y=7.5). Saves the .blend. Run headless on r105_lm.blend / r105_work.blend.
import bpy
IMG = r'C:\Users\HENRIQUE\Tools\captures\r105m_paisagem_noite.png'
b = bpy.data.objects.get('fundo_armarios_zp')
if b: b.hide_render = True; b.hide_viewport = True
old = bpy.data.objects.get('paisagem_janelas')
if old: bpy.data.objects.remove(old, do_unlink=True)
X0, X1, Z0, Z1, Y = -10.0, 10.0, -1.5, 7.5, 7.5
me = bpy.data.meshes.new('paisagem_janelas')
me.from_pydata([(X0, Y, Z0), (X1, Y, Z0), (X1, Y, Z1), (X0, Y, Z1)], [], [(0, 3, 2, 1)])   # faces the room (-y)
uv = me.uv_layers.new(name='UVMap')
for li, (u, v) in zip(range(4), [(0, 0), (0, 1), (1, 1), (1, 0)]): pass
co = {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}
for p in me.polygons:
    for li in p.loop_indices: uv.data[li].uv = co[me.loops[li].vertex_index]
me.uv_layers.new(name='lm')
m = bpy.data.materials.new('paisagem_noite'); m.use_nodes = True; nt = m.node_tree
bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(IMG, check_existing=True); tx.image.name = 'paisagem_noite.png'
nt.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
me.materials.append(m)
o = bpy.data.objects.new('paisagem_janelas', me); bpy.data.collections['Props'].objects.link(o)
bpy.ops.wm.save_mainfile()
print('PAISAGEM ok', 'backing hidden' if b else 'no backing')
