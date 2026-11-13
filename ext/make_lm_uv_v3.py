# Headless: blender -b blend/r105_work.blend --python ext/make_lm_uv_v3.py
# UV 'lm' v3 (sobre a v2): 1) solda vertices coincidentes (< 0,1 mm) antes do smart project, para faces vizinhas
# virarem uma ilha so (as "Combined Mesh" tinham cada triangulo solto = milhares de ilhas e margens);
# 2) ilhas finas sao esticadas na direcao estreita ate MIN_W texels (chanfros, molduras) e o atlas e reempacotado.
# A forma do modelo nao muda (soldar so une vertices na mesma posicao; UVs de textura sao por canto e ficam iguais).
# Salva blend/r105_lm_v3.blend.
import bpy, bmesh, time, math, collections
import numpy as np
t0 = time.time(); RES = 4096; MIN_W = 2.5; MARGIN = 0.0009; MAXSTRETCH = 25.0
objs = [o for c in ('Fit_Dining', 'Props') for o in bpy.data.collections[c].all_objects
        if o.type in ('MESH', 'CURVE') and not o.hide_render]
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.hide_set(False); o.hide_viewport = False; o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False)
bpy.ops.object.convert(target='MESH')
meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH' and len(o.data.polygons)]
f0 = sum(len(o.data.polygons) for o in meshes)
welded = 0; ORIG = {}
for o in meshes:
    ORIG[o.name] = o.data.copy()          # malha original (vertices separados, normais intactas): recebe so o UV lm no fim
    bm = bmesh.new(); bm.from_mesh(o.data); nv = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001); welded += nv - len(bm.verts)
    bm.to_mesh(o.data); bm.free()
    for u in list(o.data.uv_layers):
        if u.name in ('lm', 'luz'): o.data.uv_layers.remove(u)
    o.data.uv_layers.new(name='lm')
    o.data.uv_layers.active = o.data.uv_layers['lm']
print('LMUV3 meshes', len(meshes), 'faces', f0, '->', sum(len(o.data.polygons) for o in meshes), 'vertices soldados', welded, flush=True)
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=MARGIN, area_weight=0.6, correct_aspect=True, scale_to_bounds=False)
bpy.context.scene.tool_settings.use_uv_select_sync = True
def pack():
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(udim_source='ACTIVE_UDIM', rotate=True, margin=MARGIN, scale=True, merge_overlap=False, shape_method='AABB')
pack()
bpy.ops.object.mode_set(mode='OBJECT')

def islands(o):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table(); lm = bm.loops.layers.uv['lm']
    par = list(range(len(bm.faces)))
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for e in bm.edges:
        if len(e.link_faces) != 2: continue
        f1, f2 = e.link_faces
        u = [{l.vert.index: l[lm].uv.copy() for l in f.loops if l.vert in e.verts} for f in (f1, f2)]
        if all((u[0][k] - u[1][k]).length < 1e-6 for k in u[0]): par[find(f1.index)] = find(f2.index)
    g = collections.defaultdict(list)
    for f in bm.faces: g[find(f.index)].append(f.index)
    bm.free(); return list(g.values())

def widen():
    """estica ilhas finas; devolve quantas"""
    n = 0; widths = []
    for o in meshes:
        me = o.data; uvl = me.uv_layers['lm'].data
        for fs in islands(o):
            li = [l for fi in fs for l in me.polygons[fi].loop_indices]
            P = np.array([uvl[l].uv[:] for l in li]) * RES
            c = P.mean(0); Q = P - c
            if len(np.unique(P.round(4), axis=0)) < 3: continue
            w, V = np.linalg.eigh(Q.T @ Q)                         # V[:,0] = eixo estreito
            minor = Q @ V[:, 0]; width = minor.max() - minor.min(); widths.append(width)
            if width >= MIN_W: continue
            k = min(MIN_W / max(width, MIN_W / MAXSTRETCH), MAXSTRETCH)
            Qn = Q + np.outer(minor * (k - 1), V[:, 0])
            for l, q in zip(li, (Qn + c) / RES): uvl[l].uv = q
            n += 1
    return n, np.array(widths)

for it in range(2):
    n, W = widen()
    print('LMUV3 passada', it, 'ilhas', len(W), 'esticadas', n, 'largura p5/p50 texels', np.percentile(W, [5, 50]).round(2), flush=True)
    bpy.ops.object.mode_set(mode='EDIT'); pack(); bpy.ops.object.mode_set(mode='OBJECT')
n, W = widen()   # so mede (as ilhas ja esticadas nao mexem mais se >= MIN_W)
print('LMUV3 final ilhas', len(W), 'ainda finas', int((W < 1).sum()), 'p5/p50', np.percentile(W, [5, 50]).round(2), flush=True)
bpy.ops.object.mode_set(mode='EDIT'); pack(); bpy.ops.object.mode_set(mode='OBJECT')
# densidade: texels por metro (media ponderada por area) nas paredes grandes
dens = []
for o in meshes:
    me = o.data; uvl = me.uv_layers['lm'].data; a3 = au = 0
    for p in me.polygons:
        if p.area < 0.05: continue
        us = [uvl[l].uv for l in p.loop_indices]
        for i in range(1, len(us) - 1): au += abs((us[i] - us[0]).cross(us[i + 1] - us[0])) / 2
        a3 += p.area
    if a3 > 0: dens.append((a3, math.sqrt(au / a3) * RES))
dens.sort(reverse=True)
print('LMUV3 texels/m nas superficies grandes (top 5 objetos por area):', [round(d, 1) for a, d in dens[:5]], flush=True)
# devolve a malha ORIGINAL (sem solda) a cada objeto, so com o UV lm copiado por face (casando pelo centro e pelos vertices)
from mathutils import Vector
miss = 0
for o in meshes:
    wd = o.data; od = ORIG[o.name]
    wl = wd.uv_layers['lm'].data
    key = lambda co: (round(co.x, 4), round(co.y, 4), round(co.z, 4))
    idx = {}
    for p in wd.polygons:
        idx[key(p.center)] = p
    for u in list(od.uv_layers):
        if u.name in ('lm', 'luz'): od.uv_layers.remove(u)
    ol = od.uv_layers.new(name='lm').data
    for p in od.polygons:
        q = idx.get(key(p.center))
        if q is None or q.loop_total != p.loop_total: miss += 1; continue
        wpos = {key(wd.vertices[wd.loops[l].vertex_index].co): wl[l].uv.copy() for l in q.loop_indices}
        for l in p.loop_indices:
            uv = wpos.get(key(od.vertices[od.loops[l].vertex_index].co))
            if uv is not None: ol[l].uv = uv
    o.data = od
print('LMUV3 UV copiado para a malha original; faces sem par (degeneradas):', miss, flush=True)
bpy.ops.wm.save_as_mainfile(filepath=r'C:\Users\HENRIQUE\Tools\re1mod\blend\r105_lm_v3.blend')
print('LMUV3 done sec', round(time.time() - t0), flush=True)
