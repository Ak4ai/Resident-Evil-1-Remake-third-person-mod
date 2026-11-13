f = r'C:\Users\HENRIQUE\Tools\re1mod\ext\preview_rms4.py'
p = open(f).read()
if 'make_pose_cam' not in p:
    old = "for n in names:\n    sc.camera = bpy.data.objects[n];"
    assert old in p
    new = r'''import math, mathutils
def make_pose_cam():
    x, y, z, yaw, pit, fov = [float(v) for v in open(r'C:\Users\HENRIQUE\Tools\captures\pose.txt').read().split()]
    cp = math.cos(pit); fd = (math.sin(yaw) * cp, math.sin(pit), math.cos(yaw) * cp)     # game dir (x, y-up, z)
    d = mathutils.Vector((fd[0], fd[2], fd[1]))                                          # -> blender (x, y, z-up)
    cd = bpy.data.cameras.new('posecam'); cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(fov); cd.clip_start = 0.05; cd.clip_end = 200
    co = bpy.data.objects.new('pose', cd); bpy.context.scene.collection.objects.link(co)
    co.location = (x / 100.0, z / 100.0, y / 100.0); co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return co
sc.render.resolution_x = 640; sc.render.resolution_y = 360
for n in names:
    if n == 'pose': make_pose_cam()
    sc.camera = bpy.data.objects[n];'''
    p = p.replace(old, new)
    open(f, 'w').write(p)
print('ok')
