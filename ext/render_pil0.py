# Render de conferencia da pilastra pil_clean_0 (canto com a parede), mesma camera nos dois arquivos.
import bpy, sys
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
cam = bpy.data.objects.new('cam_conf', bpy.data.cameras.new('cam_conf')); sc.collection.objects.link(cam)
cam.location = Vector((5.3, -1.6, 1.7)); d = Vector((6.75, -3.6, 1.6)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = 28
sc.camera = cam
sc.render.engine = 'CYCLES'; sc.cycles.samples = 64; sc.cycles.use_denoising = True
try:
    p = bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type = 'OPTIX'; p.get_devices()
    for dv in p.devices: dv.use = True
    sc.cycles.device = 'GPU'
except Exception as e: print('gpu', e)
sc.render.resolution_x = 900; sc.render.resolution_y = 1100; sc.render.resolution_percentage = 100
sc.render.filepath = out; bpy.ops.render.render(write_still=True); print('saved', out)
