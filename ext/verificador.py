# Verificador do modelo antes do bake (NAO salva o .blend).
# Uso: blender -b blend/r105_lm_v2.blend --python ext/verificador.py [-- N_CAMERAS]
# Acha, em coordenadas do mundo:
#   1 ZFIGHT    faces de objetos diferentes no mesmo plano (< TOL_Z) e voltadas para o mesmo lado -> piscam no jogo
#   2 ESCONDIDA faces cuja frente esta tapada por dentro de outro objeto (o raio pela normal bate nas costas de uma face):
#               saem pretas no bake e vazam para a beirada visivel (ex.: parede atras da pilastra)
#   3 FINA      ilhas do UV 'lm' com largura < MIN_TEX texels (ex.: chanfro de 0,25 texel): o bake nao escreve luz nelas
#   4 FRESTA    bordas abertas que nao encostam em nenhuma outra superficie (< TOL_F): deixam ver o vazio
# Saida: preview/verif/relatorio.txt, verif.json e, para as N cameras que mais veem problemas,
#        camXX_a.png (cores sobre cinza) e camXX_b.png (raio-X, mostra as escondidas).
import bpy, bmesh, sys, json, os, math, collections
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
POSE = 'pose' in ARGS   # -- pose : renderiza so da camera atual do jogo (captures/pose.txt)
NCAM = next((int(a) for a in ARGS if a.isdigit()), 6)
OUT = r'C:\Users\HENRIQUE\Tools\re1mod\preview\verif'; os.makedirs(OUT, exist_ok=True)
LM_RES = 4096; MIN_TEX = 1.0; TOL_Z = 0.002; TOL_F = 0.003; HID_DIST = 1.0
COL = {0: (0.55, 0.55, 0.55, 1), 1: (1, 0.05, 0.05, 1), 2: (0.55, 0.55, 0.55, 1), 3: (1, 0.85, 0, 1), 4: (0.55, 0.55, 0.55, 1),   # FRESTA so no relatorio (teste ainda nao confiavel)
       5: (1, 0, 1, 1), 6: (1, 0.45, 0, 1), 7: (0, 0.9, 1, 1), 8: (1, 0.4, 0.7, 1)}
NOME = {1: 'ZFIGHT', 2: 'ESCONDIDA', 3: 'FINA', 4: 'FRESTA', 5: 'UV_SOBREPOSTO', 6: 'UV_QUEBRADO', 7: 'FORA_DO_JOGO', 8: 'QUASE_COLADA'}
#   5 UV_SOBREPOSTO ilhas diferentes do UV 'lm' ocupando os mesmos texels: o bake de uma pinta por cima da outra (parede preta)
#   6 UV_QUEBRADO   canto do UV fora do atlas ou em (0,0), ou face com UV desproporcional ao tamanho real (triangulo gigante)
#   7 FORA_DO_JOGO  objeto visivel no Blender que nao entra no export/bake (fora de Fit_Dining/Props ou sem UV lm)
#   8 QUASE_COLADA  superficies de objetos diferentes a 2-15 mm uma da outra, quase paralelas: piscam/tremem de longe
EXPORT_COLS = ('Fit_Dining', 'Props')

dg = bpy.context.evaluated_depsgraph_get()
objs = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.visible_get() and not o.hide_render]
# ---- tudo junto em um BVH (mundo) ----
V = []; F = []; fo = []; fl = []   # verts, faces, face->obj index, face->local poly index
for oi, o in enumerate(objs):
    me = o.data; mw = o.matrix_world; b = len(V)
    V += [mw @ v.co for v in me.vertices]
    for p in me.polygons:
        F.append([b + i for i in p.vertices]); fo.append(oi); fl.append(p.index)
bvh = BVHTree.FromPolygons(V, F, all_triangles=False, epsilon=0.0)
fnorm = []; fcent = []; farea = []
for f in F:
    P = [V[i] for i in f]
    n = Vector((0, 0, 0))
    for i in range(1, len(P) - 1): n += (P[i] - P[0]).cross(P[i + 1] - P[0])
    a = n.length / 2; fnorm.append(n.normalized() if a > 0 else n); farea.append(a); fcent.append(sum(P, Vector()) / len(P))
print('faces', len(F), 'objetos', len(objs), flush=True)
flag = [0] * len(F)

def samples(fi):
    P = [V[i] for i in F[fi]]; c = fcent[fi]
    return [c] + [c + (p - c) * 0.8 for p in P[:4]]

# ---- 1 ZFIGHT e 2 ESCONDIDA (raios curtos) ----
nz = nh = 0
for fi in range(len(F)):
    n = fnorm[fi]
    if farea[fi] < 1e-6: continue
    # z-fight: de um ponto 1 mm a frente, raio para tras ate 1 mm atras do plano; outra face de outro objeto, mesma orientacao
    hits = 0; tot = 0
    for s in samples(fi):
        tot += 1
        loc, nn, idx, d = bvh.ray_cast(s + n * 0.001, -n, 0.001 + TOL_Z)
        if idx is not None and idx != fi and fnorm[idx].dot(n) > 0.99: hits += 1   # inclui faces do MESMO objeto (ex.: roupa da estatua)
    if hits >= 2: flag[fi] = 1; nz += 1; continue
    # escondida: raios pela normal (e inclinados 30 graus) batem nas COSTAS de uma face
    t1 = n.orthogonal().normalized(); t2 = n.cross(t1)
    dirs = [n] + [(n + (t1 * a + t2 * b) * 0.577).normalized() for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    # varios pontos por face (grade em cada triangulo do leque): pega faces so PARTE escondidas, como a parede atras da pilastra
    P = [V[i] for i in F[fi]]; pts = [fcent[fi]]
    if farea[fi] > 0.01:
        k = 6 if farea[fi] > 0.2 else 3
        for t in range(1, len(P) - 1):
            for a in range(k + 1):
                for b in range(k + 1 - a):
                    w0 = (a + 0.33) / (k + 1); w1 = (b + 0.33) / (k + 1)
                    if w0 + w1 < 1: pts.append(P[0] * (1 - w0 - w1) + P[t] * w0 + P[t + 1] * w1)
    for pt in pts:
        back = 0
        for dv in dirs:
            loc, nn, idx, d = bvh.ray_cast(pt + n * 0.001, dv, HID_DIST)
            if idx is not None and idx != fi and fnorm[idx].dot(dv) > 0.2: back += 1
        if back >= 4: flag[fi] = 2; nh += 1; break
print('zfight', nz, 'escondidas', nh, flush=True)

# ---- 3 FINA (ilhas do UV lm) e 4 FRESTA (bordas abertas soltas) ----
nt = nf = 0; base = 0
for oi, o in enumerate(objs):
    me = o.data; mw = o.matrix_world
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    lm = bm.loops.layers.uv.get('lm')
    if lm is not None:
        par = list(range(len(bm.faces)))
        def find(x):
            while par[x] != x: par[x] = par[par[x]]; x = par[x]
            return x
        # mesma ilha = faces que dividem uma aresta com a mesma POSICAO e o mesmo UV lm (funciona com triangulos soltos)
        ek = {}
        for f in bm.faces:
            ls = list(f.loops)
            for i, l in enumerate(ls):
                m_ = ls[(i + 1) % len(ls)]
                a = (tuple(round(c, 4) for c in l.vert.co), round(l[lm].uv.x, 6), round(l[lm].uv.y, 6))
                b = (tuple(round(c, 4) for c in m_.vert.co), round(m_[lm].uv.x, 6), round(m_[lm].uv.y, 6))
                k = (a, b) if a < b else (b, a)
                if k in ek: par[find(f.index)] = find(ek[k])
                else: ek[k] = f.index
        isl = collections.defaultdict(list)
        for f in bm.faces: isl[find(f.index)].append(f)
        for fs in isl.values():
            A = 0.0; edges = collections.Counter()
            for f in fs:
                us = [l[lm].uv for l in f.loops]
                for i in range(1, len(us) - 1): A += abs((us[i] - us[0]).cross(us[i + 1] - us[0])) / 2
                for l in f.loops:
                    k = tuple(sorted(((round(l[lm].uv.x, 7), round(l[lm].uv.y, 7)), (round(l.link_loop_next[lm].uv.x, 7), round(l.link_loop_next[lm].uv.y, 7)))))
                    edges[k] += 1
            per = sum((Vector(a) - Vector(b)).length for (a, b), c in edges.items() if c == 1)
            w = 2 * A / per * LM_RES if per > 0 else 0
            a3 = sum(f.calc_area() for f in fs) * (mw.to_scale().x ** 2)
            if w < MIN_TEX and a3 > 0.002:          # ignora miudezas (< 20 cm2) como pregos e franjas
                for f in fs:
                    gi = base + f.index
                    if flag[gi] == 0: flag[gi] = 3; nt += 1
    for e in bm.edges:
        if not e.is_boundary or e.calc_length() < 0.02: continue
        m = mw @ ((e.verts[0].co + e.verts[1].co) / 2)
        f0 = base + e.link_faces[0].index
        # procura outra superficie perto da borda (fora da propria face)
        out_dir = (m - fcent[f0]); out_dir -= fnorm[f0] * out_dir.dot(fnorm[f0])   # para fora da face, no plano dela
        od = out_dir.normalized(); nn0 = fnorm[f0]; p0 = m + od * 0.0005
        near = False
        tests = [(p0 + nn0 * 0.001, -nn0, 0.002 + TOL_F), (p0 - nn0 * 0.001, nn0, 0.002 + TOL_F)]   # vizinho no mesmo plano
        tests += [(p0, dv, TOL_F + 0.001) for dv in (od, nn0, -nn0, (od + nn0).normalized(), (od - nn0).normalized())]  # superficie em angulo
        for org, dv, L in tests:
            loc, nn, idx, d = bvh.ray_cast(org, dv, L)
            if idx is not None and idx != f0: near = True; break
        if not near:   # coberta por outra peca na frente (ex.: borda de parede atras da cornija) nao aparece
            cov = 0
            for dv in (nn0, (nn0 + od).normalized(), (nn0 - od).normalized()):
                loc, nn, idx, d = bvh.ray_cast(p0 + nn0 * 0.0005, dv, 0.3)
                if idx is not None and idx != f0: cov += 1
            near = cov == 3
        if not near and flag[f0] == 0: flag[f0] = 4; nf += 1
    base += len(me.polygons); bm.free()
print('finas', nt, 'frestas', nf, flush=True)

# ---- 5/6/7: UV do lightmap (sobreposicao, quebrado) e objetos fora do export ----
import numpy as np
exp_set = {o.name for c in EXPORT_COLS if c in bpy.data.collections for o in bpy.data.collections[c].all_objects}
R = 1024; owner = np.full((R, R), -1, np.int64); claim = collections.defaultdict(list)   # texel -> faces (so os disputados)
nu = no = ne = 0; base = 0; isl_id = 0
for oi, o in enumerate(objs):
    me = o.data; nP = len(me.polygons)
    lm = me.uv_layers.get('lm')
    if o.name not in exp_set or lm is None:
        for p in me.polygons:
            if flag[base + p.index] == 0: flag[base + p.index] = 7; ne += 1
        base += nP; continue
    uv = np.array([d.uv[:] for d in lm.data], np.float64)
    # ilhas por posicao+UV (mesma regra do teste FINA)
    par = list(range(nP))
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    ek = {}
    for p in me.polygons:
        li = list(p.loop_indices); n_ = len(li)
        for i in range(n_):
            l0, l1 = li[i], li[(i + 1) % n_]
            a = (tuple(np.round(me.vertices[me.loops[l0].vertex_index].co, 4)), tuple(np.round(uv[l0], 6)))
            b = (tuple(np.round(me.vertices[me.loops[l1].vertex_index].co, 4)), tuple(np.round(uv[l1], 6)))
            k = (a, b) if a < b else (b, a)
            if k in ek: par[find(p.index)] = find(ek[k])
            else: ek[k] = p.index
    roots = {}
    for p in me.polygons:
        gi = base + p.index; us = uv[list(p.loop_indices)]
        r_ = find(p.index); iid = roots.setdefault(r_, isl_id + len(roots))
        bad = (us.min() < -0.001 or us.max() > 1.001 or np.any(np.all(np.abs(us) < 1e-7, axis=1)))
        au = 0.0
        for i in range(1, len(us) - 1): au += abs(np.cross(us[i] - us[0], us[i + 1] - us[0])) / 2
        dens = math.sqrt(au / max(farea[gi], 1e-9)) * LM_RES   # texels por metro
        if bad or (farea[gi] > 1e-4 and dens > 400):           # 400 texels/m = 20x a media: UV esticado demais
            if flag[gi] in (0, 3): flag[gi] = 6; nu += 1
        # rasteriza a face no atlas reduzido (1024): centro de cada texel coberto
        P2 = us * R; x0, y0 = np.floor(P2.min(0)).astype(int); x1, y1 = np.ceil(P2.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, R); y1 = min(y1, R)
        if x1 <= x0 or y1 <= y0 or (x1 - x0) * (y1 - y0) > R * R + 1: continue
        gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        Q = np.stack([gx.ravel(), gy.ravel()], 1); inside = np.zeros(len(Q), bool)
        for i in range(1, len(P2) - 1):
            A, B, C = P2[0], P2[i], P2[i + 1]
            d1 = (Q[:, 0] - B[0]) * (A[1] - B[1]) - (A[0] - B[0]) * (Q[:, 1] - B[1])
            d2 = (Q[:, 0] - C[0]) * (B[1] - C[1]) - (B[0] - C[0]) * (Q[:, 1] - C[1])
            d3 = (Q[:, 0] - A[0]) * (C[1] - A[1]) - (C[0] - A[0]) * (Q[:, 1] - A[1])
            inside |= ~(((d1 < 0) | (d2 < 0) | (d3 < 0)) & ((d1 > 0) | (d2 > 0) | (d3 > 0)))
        Q = Q[inside].astype(int)
        if not len(Q): continue
        cur = owner[Q[:, 1], Q[:, 0]]
        clash = (cur >= 0) & (cur != iid)
        for (tx, ty) in Q[clash]: claim[(tx, ty)].append(gi)
        free_ = cur < 0; owner[Q[free_, 1], Q[free_, 0]] = iid
        if clash.any(): claim[('face', gi)] = [int(c) for c in np.unique(cur[clash])]
    isl_id += len(roots); base += nP
# marca as duas partes de cada disputa
isl_faces = collections.defaultdict(list)
over = set(gi for k, v in claim.items() if k[0] != 'face' for gi in v)
for gi in over:
    if flag[gi] in (0, 3): flag[gi] = 5; no += 1
print('uv quebrado', nu, 'uv sobreposto', no, 'fora do jogo', ne, flush=True)

# ---- 8: superficies quase coladas (2-15 mm, quase paralelas, objetos diferentes) ----
nq = 0
for fi in range(len(F)):
    if flag[fi] or farea[fi] < 1e-5: continue
    n = fnorm[fi]; hit = 0
    for s in samples(fi):
        for sgn in (1, -1):
            loc, nn, idx, d = bvh.ray_cast(s + n * sgn * 0.0005, n * sgn, 0.015)
            if idx is not None and idx != fi and fo[idx] != fo[fi] and d > 0.0015 and abs(fnorm[idx].dot(n)) > 0.97: hit += 1; break
    if hit >= 3: flag[fi] = 8; nq += 1
print('quase coladas', nq, flush=True)

# ---- relatorio ----
porobj = collections.defaultdict(lambda: collections.Counter())
for fi, k in enumerate(flag):
    if k: porobj[objs[fo[fi]].name][NOME[k]] += 1
with open(os.path.join(OUT, 'relatorio.txt'), 'w', encoding='utf-8') as fh:
    fh.write('VERIFICADOR %s\nfaces %d\n' % (bpy.data.filepath, len(F)))
    for k in (1, 2, 3, 4, 5, 6, 7, 8):
        ar = sum(farea[i] for i in range(len(F)) if flag[i] == k)
        fh.write('%-10s %6d faces  %.2f m2\n' % (NOME[k], flag.count(k), ar))
    fh.write('\npor objeto:\n')
    for nm, c in sorted(porobj.items(), key=lambda x: -sum(x[1].values())):
        fh.write('  %-45s %s\n' % (nm, dict(c)))
json.dump({'objs': [o.name for o in objs], 'flag': [[fo[i], fl[i], k] for i, k in enumerate(flag) if k]}, open(os.path.join(OUT, 'verif.json'), 'w'))

# ---- cores por face + render nas cameras que mais veem problemas ----
base = 0
for oi, o in enumerate(objs):
    me = o.data
    at = me.color_attributes.new('verif', 'BYTE_COLOR', 'CORNER')
    for p in me.polygons:
        c = COL[flag[base + p.index]]
        for li in p.loop_indices: at.data[li].color = c
    me.color_attributes.active_color = at; base += len(me.polygons)
sc = bpy.context.scene
cams = [o for o in sc.objects if o.type == 'CAMERA']
probs = [fcent[i] for i, k in enumerate(flag) if k]
step = max(1, len(probs) // 4000); probs = probs[::step]
score = []
for c in cams:
    s = 0
    for p in probs:
        v = world_to_camera_view(sc, c, p)
        if 0 < v.x < 1 and 0 < v.y < 1 and 0 < v.z < 12:
            # visivel? raio da camera ate o ponto
            d = p - c.matrix_world.translation; L = d.length
            loc, nn, idx, dd = bvh.ray_cast(c.matrix_world.translation, d.normalized(), L - 0.01)
            s += 1 if idx is None else 0.15
    score.append((s, c.name))
score.sort(reverse=True)
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'VERTEX'; sh.show_cavity = False; sh.show_backface_culling = True
sc.render.resolution_x = 1280; sc.render.resolution_y = 960; sc.render.resolution_percentage = 100
render_list = score[:NCAM]
if POSE:   # camera do jogo (captures/pose.txt); a imagem sai espelhada na horizontal em relacao ao jogo -> desespelhada no fim
    import math
    x, y, z, yaw, pit, fov = [float(v) for v in open(os.environ.get('POSE', r'C:\Users\HENRIQUE\Tools\captures\pose.txt')).read().split()]
    cp = math.cos(pit); d = Vector((math.sin(yaw) * cp, math.cos(yaw) * cp, math.sin(pit)))
    cd = bpy.data.cameras.new('pose'); cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(fov); cd.clip_start = 0.05; cd.clip_end = 200
    co = bpy.data.objects.new('pose', cd); sc.collection.objects.link(co)
    co.location = (x / 100.0, z / 100.0, y / 100.0); co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    render_list = [(0, 'pose')]
for s, nm in render_list:
    sc.camera = sc.objects[nm]
    sh.show_xray = False; sc.render.filepath = os.path.join(OUT, nm + '_a.png'); bpy.ops.render.render(write_still=True)
    sh.show_xray = True; sh.xray_alpha = 0.35; sc.render.filepath = os.path.join(OUT, nm + '_b.png'); bpy.ops.render.render(write_still=True)
    if nm == 'pose':
        try:
            import numpy as np
            for suf in ('_a', '_b'):
                im = bpy.data.images.load(os.path.join(OUT, nm + suf + '.png')); w, h = im.size
                px = np.array(im.pixels[:]).reshape(h, w, 4)[:, ::-1].copy(); im.pixels = px.ravel(); im.save()
        except Exception as e: print('flip', e)
    print('render', nm, round(s, 1), flush=True)
with open(os.path.join(OUT, 'relatorio.txt'), 'a', encoding='utf-8') as fh:
    fh.write('\ncameras (pontuacao de problemas visiveis): %s\n' % [(n, round(s)) for s, n in score[:12]])
print('FIM', flush=True)
