import bpy, time
pr=bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type='OPTIX'; pr.get_devices()
for d in pr.devices: d.use=(d.type=='OPTIX')
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='GPU'; sc.cycles.samples=48; sc.cycles.use_denoising=False
sc.render.resolution_x=640; sc.render.resolution_y=480; sc.view_settings.view_transform='Standard'; sc.view_settings.exposure=2.0
w=sc.world; bg=next((n for n in w.node_tree.nodes if n.type=='BACKGROUND'),None); ws=bg.inputs['Strength'].default_value; wc=tuple(bg.inputs['Color'].default_value)
print('WORLD',ws,wc)
lights={L.name:L for L in bpy.data.collections['Luz_r105'].all_objects}
BASE=('lustre_W','lustre_E','lustre_alto','fill_leste','fundo_oeste','lua')
def setup(on,world):
    for n,L in lights.items(): L.hide_render = n not in on
    bg.inputs['Strength'].default_value = ws if world else 0
variants={'base_all':(BASE,True),'base_noworld':(BASE,False),'world_only':((),True),'lustres':(('lustre_W','lustre_E','lustre_alto'),False),'fill':(('fill_leste','fundo_oeste'),False),'lua':(('lua',),False)}
for cam in ('cam16',):
    sc.camera=bpy.data.objects[cam]
    for k,(on,wd) in variants.items():
        setup(on,wd); sc.render.filepath=r'C:\Users\HENRIQUE\Tools\re1mod\preview\disc_%s.png'%k; bpy.ops.render.render(write_still=True); print('R',k,flush=True)
