# Assa a cor procedural da Porta_Meshy (nos de Wave/Noise) numa imagem comum no UV 'UVMap', para o jogo poder usar.
# Liga essa imagem ao Base Color do material, salva em captures e registra no export_names.pkl. Salva o .blend.
# Uso: blender -b blend/r105_work.blend --python ext/bake_porta_tex.py
import bpy, os, pickle
SIZE = 1024
CAP = r'C:\Users\HENRIQUE\Tools\captures'; NAMES = r'C:\Users\HENRIQUE\Tools\re1mod\ext\export_names.pkl'
o = bpy.data.objects['Porta_Meshy']; me = o.data
mt = o.material_slots[0].material; nt = mt.node_tree
img = bpy.data.images.get('porta_meshy_cor') or bpy.data.images.new('porta_meshy_cor', SIZE, SIZE, alpha=False)
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; nt.nodes.active = tex
me.uv_layers.active = me.uv_layers['UVMap']
# o UVMap do Meshy vinha esmagado numa tira: refaz um UV limpo so desta peca antes de assar a cor
import math
for x in bpy.context.selected_objects: x.select_set(False)
o.select_set(True); bpy.context.view_layer.objects.active = o
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0, correct_aspect=True, scale_to_bounds=True)
bpy.ops.object.mode_set(mode='OBJECT')
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 16
pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = 'OPTIX'; pr.get_devices()
for d in pr.devices: d.use = (d.type == 'OPTIX')
sc.cycles.device = 'GPU'
b = sc.render.bake; b.use_pass_direct = False; b.use_pass_indirect = False; b.use_pass_color = True; b.margin = 8; b.target = 'IMAGE_TEXTURES'
for x in bpy.context.selected_objects: x.select_set(False)
o.select_set(True); bpy.context.view_layer.objects.active = o
bpy.ops.object.bake(type='DIFFUSE')
# a imagem assada vira a cor do material (o export pega a imagem ligada ao Base Color)
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
for l in list(bsdf.inputs['Base Color'].links): nt.links.remove(l)
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
fn = 'r105m_porta_meshy_cor.png'
img.filepath_raw = os.path.join(CAP, fn); img.file_format = 'PNG'; img.save()
img.pack()
names = pickle.load(open(NAMES, 'rb')); names[img.name] = fn; pickle.dump(names, open(NAMES, 'wb'))
bpy.ops.wm.save_mainfile()
print('PORTA textura assada', fn, flush=True)
