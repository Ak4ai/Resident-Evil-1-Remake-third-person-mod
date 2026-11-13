# Render de teste da luz das janelas (so a luz, sem as outras): blender -b blend/r105_lm_v3.blend --python ext/render_janela.py -- <luz> <camera> <saida.png>
import bpy, sys
luz, camn, out = sys.argv[sys.argv.index('--') + 1:][:3]
sc = bpy.context.scene
for L in [o for o in bpy.data.objects if o.type == 'LIGHT']: L.hide_render = (L.name != luz)
for o in bpy.data.objects:
    if o.type == 'MESH' and (o.name.startswith('fundo_') or 'paisagem' in o.name.lower()): o.visible_shadow = False
w = sc.world
if w and w.node_tree:
    for n in w.node_tree.nodes:
        if n.type == 'BACKGROUND': n.inputs['Strength'].default_value = 0
if camn == 'planta':   # vista de cima, de dentro da sala (abaixo do teto), para ver as manchas no chao
    cd = bpy.data.cameras.new('planta'); cd.type = 'ORTHO'; cd.ortho_scale = 21; cd.clip_start = 0.05; cd.clip_end = 4.0
    co = bpy.data.objects.new('planta', cd); sc.collection.objects.link(co); co.location = (0, 0, 3.3); co.rotation_euler = (0, 0, 0)
sc.camera = sc.objects[camn]
pr = bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type = 'OPTIX'; pr.get_devices()
for d in pr.devices: d.use = (d.type == 'OPTIX')
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 48; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = 0
sc.render.resolution_x = 960; sc.render.resolution_y = 720; sc.render.filepath = out
bpy.ops.render.render(write_still=True); print('saved', out)
