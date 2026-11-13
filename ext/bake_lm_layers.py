# Headless: blender -b blend/r105_bake.blend --python ext/bake_lm_layers.py -- [layer ...]
# Bakes light-only (DIFFUSE direct+indirect, no colour) into the 'lm' UV, one pass per light group, on the RTX (OptiX).
# Writes lm_layers/<layer>.npy (float16 HxWx3 linear). Does NOT save the .blend.
import bpy, sys, time, numpy as np
import os
SIZE=int(os.environ.get('LM_SIZE','4096')); SAMPLES=int(os.environ.get('LM_SAMPLES','192'))
GROUPS={'base':lambda n:n in('lustre_W','lustre_E','lustre_alto','fill_leste','fundo_oeste','lua'),
        'lareira':lambda n:n=='lareira',
        'velas':lambda n:n.startswith('candelabro_'),
        'arandelas':lambda n:n.startswith('arandela_'),
        'relampago':lambda n:n=='relampago',   # sol forte branco-azulado pela janela (direcao = voldir do mod); vai no alfa da base
        'luar':lambda n:n=='luar'}             # mesmo sol, fraco: manchas das janelas; vai no alfa da lareira
OUTSIDE=('relampago','luar')   # luz de fora: planos de fundo/paisagem atras das janelas nao podem fazer sombra
for _n in ('lustre_W','lustre_E','lustre_alto','fill_leste','fundo_oeste','lua'):
    GROUPS['t_'+_n]=(lambda n,_n=_n: n==_n)
want=sys.argv[sys.argv.index('--')+1:] or list(GROUPS)
pr=bpy.context.preferences.addons['cycles'].preferences
pr.compute_device_type='OPTIX'; pr.get_devices()
for d in pr.devices: d.use=(d.type=='OPTIX')
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='GPU'; sc.cycles.samples=SAMPLES
sc.cycles.use_denoising=False; sc.cycles.bake_type='DIFFUSE'
b=sc.render.bake; b.use_pass_direct=True; b.use_pass_indirect=True; b.use_pass_color=False
b.target='IMAGE_TEXTURES'; b.margin=6; b.use_clear=not os.environ.get('LM_ONLY')
objs=[o for c in ('Fit_Dining','Props') for o in bpy.data.collections[c].all_objects
      if o.type=='MESH' and not o.hide_render and o.data.uv_layers.get('lm')]
ONLY=os.environ.get('LM_ONLY')
if ONLY: objs=[o for o in objs if o.name.startswith(ONLY)]
print('BAKE objs',len(objs),'only',ONLY)
img=bpy.data.images.new('lm_tmp',SIZE,SIZE,float_buffer=True,alpha=False)
mats=set()
for o in objs:
    o.data.uv_layers.active=o.data.uv_layers['lm']
    for s in o.material_slots:
        if s.material: mats.add(s.material)
for m in mats:
    m.use_nodes=True; nt=m.node_tree
    n=nt.nodes.new('ShaderNodeTexImage'); n.image=img; n.name='LMBAKE'; nt.nodes.active=n
lights=list(bpy.data.collections['Luz_r105'].all_objects)
w=sc.world; wstr=None
if w and w.use_nodes:
    bg=next((n for n in w.node_tree.nodes if n.type=='BACKGROUND'),None)
    if bg: wstr=bg.inputs['Strength'].default_value
OUTP=(r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\%s.npy' if SIZE==4096 else r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\small_%s.npy')
for layer in want:
    t=time.time()
    for L in lights: L.hide_render=not GROUPS[layer](L.name)
    for o in bpy.data.objects:
        if o.type=='MESH' and (o.name.startswith('fundo_') or 'paisagem' in o.name.lower()): o.visible_shadow=layer not in OUTSIDE
    if w and wstr is not None: bg.inputs['Strength'].default_value=wstr if layer=='base' else 0
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    if ONLY:
        prev=np.load(OUTP%layer).astype(np.float32); px=np.ones((SIZE,SIZE,4),np.float32); px[:,:,:3]=prev; img.pixels.foreach_set(px.ravel()); img.update()
    bpy.ops.object.bake(type='DIFFUSE')
    a=np.empty(SIZE*SIZE*4,np.float32); img.pixels.foreach_get(a)
    a=a.reshape(SIZE,SIZE,4)[:,:,:3]
    np.save(OUTP%layer,a.astype(np.float16))
    print('LAYER',layer,'sec',round(time.time()-t),'max',float(a.max()),'p99',float(np.percentile(a[a.sum(2)>0],99)),flush=True)
