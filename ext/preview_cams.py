# Headless quick preview: blender -b blend/r105_lm.blend --python ext/preview_cams.py -- cam3 cam10 ...
# Cycles on the RTX, 640x360, 24 samples + OptiX denoise. All lights on. Writes preview/<cam>.png. Nothing is saved to the .blend.
import bpy, sys, time
names=sys.argv[sys.argv.index('--')+1:]
pr=bpy.context.preferences.addons['cycles'].preferences; pr.compute_device_type='OPTIX'; pr.get_devices()
for d in pr.devices: d.use=(d.type=='OPTIX')
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='GPU'; sc.cycles.samples=24
sc.cycles.use_denoising=True; sc.cycles.denoiser='OPENIMAGEDENOISE' if False else 'OPTIX'
sc.render.resolution_x=640; sc.render.resolution_y=480; sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG'
print('CAMS',[o.name for o in bpy.data.objects if o.type=='CAMERA'][:50])
for n in names:
    o=bpy.data.objects.get(n)
    if not o: print('NOCAM',n); continue
    sc.camera=o; t=time.time(); sc.render.filepath=r'C:\Users\HENRIQUE\Tools\re1mod\preview\%s.png'%n
    bpy.ops.render.render(write_still=True); print('RENDER',n,round(time.time()-t,1),'s',flush=True)
