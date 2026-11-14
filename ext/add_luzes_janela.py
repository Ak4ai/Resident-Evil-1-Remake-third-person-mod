# Adiciona ao Luz_r105 os sois 'relampago' e 'luar' na direcao do feixe de luar do mod (voldir padrao -0.22 -0.62 -1.0,
# coordenadas do jogo x, y-cima, z -> blender x, z, y). Salva o .blend aberto.
import bpy, math
from mathutils import Vector
col = bpy.data.collections['Luz_r105']
gd = Vector((-0.22, -0.62, -1.0)); d = Vector((gd.x, gd.z, gd.y)).normalized()
for nm, colr, en, ang in (('relampago', (0.80, 0.88, 1.0), 6.0, 1.0), ('luar', (0.55, 0.65, 1.0), 0.6, 0.5)):
    if nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm])
    L = bpy.data.lights.new(nm, 'SUN'); L.color = colr; L.energy = en; L.angle = math.radians(ang)
    o = bpy.data.objects.new(nm, L); col.objects.link(o); o.location = (0, 0, 10)
    o.rotation_euler = (-d).to_track_quat('Z', 'Y').to_euler()
bpy.ops.wm.save_mainfile(); print('LUZES janela ok')
