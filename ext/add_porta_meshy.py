# Coloca a porta do Meshy (ao lado da lareira) no export do jogo: move para Fit_Dining, reduz para ~TARGET faces
# (Decimate, mantem UV/forma), salva a textura dela em captures e registra o nome em export_names.pkl. Salva o .blend.
# Uso: blender -b blend/r105_work.blend --python ext/add_porta_meshy.py
import bpy, os, re, pickle
TARGET = 20000
CAP = r'C:\Users\HENRIQUE\Tools\captures'; NAMES = r'C:\Users\HENRIQUE\Tools\re1mod\ext\export_names.pkl'
o = bpy.data.objects['Porta_Meshy']
fit = bpy.data.collections['Fit_Dining']
if fit not in o.users_collection:
    for c in list(o.users_collection): c.objects.unlink(o)
    fit.objects.link(o)
o.hide_render = False; o.hide_set(False); o.hide_viewport = False
n0 = len(o.data.polygons)
if n0 > TARGET * 1.2:
    m = o.modifiers.new('dec', 'DECIMATE'); m.ratio = TARGET / n0; m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = o
    for x in bpy.context.selected_objects: x.select_set(False)
    o.select_set(True)
    bpy.ops.object.modifier_apply(modifier='dec')
print('PORTA faces', n0, '->', len(o.data.polygons), flush=True)
# textura: a imagem ligada ao Base Color do material
names = pickle.load(open(NAMES, 'rb'))
for s in o.material_slots:
    mt = s.material
    if not mt or not mt.node_tree: continue
    bsdf = next((n for n in mt.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf or not bsdf.inputs['Base Color'].is_linked: continue
    nd = bsdf.inputs['Base Color'].links[0].from_node
    for _ in range(4):
        if nd.type == 'TEX_IMAGE': break
        ins = [i for i in nd.inputs if i.is_linked]
        if not ins: break
        nd = ins[0].links[0].from_node
    if nd.type != 'TEX_IMAGE' or not nd.image: continue
    img = nd.image
    fn = 'r105m_' + re.sub(r'[^A-Za-z0-9_]+', '_', os.path.splitext(img.name)[0])[:40] + '.png'
    sc = bpy.context.scene; vt = sc.view_settings.view_transform; sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    img.save_render(os.path.join(CAP, fn), scene=sc); sc.view_settings.view_transform = vt
    names[img.name] = fn
    print('PORTA textura', img.name, '->', fn, img.size[:], flush=True)
pickle.dump(names, open(NAMES, 'wb'))
bpy.ops.wm.save_mainfile()
print('PORTA ok', bpy.data.filepath, flush=True)
