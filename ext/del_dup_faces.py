# Remove sobreposicao de faces dentro de um objeto (z-fighting): para cada par no mesmo plano (< 1 mm), voltado para o
# mesmo lado, corta a face MENOR pelas arestas da maior e apaga so os pedacos dela que ficam por cima da maior.
# A parte da menor que nao esta sobreposta continua (nunca abre buraco). Salva o .blend aberto.
# Uso: blender -b <arquivo.blend> --python ext/del_dup_faces.py -- "<nome do objeto>" [...]
import bpy, bmesh, sys
from mathutils.bvhtree import BVHTree
names = sys.argv[sys.argv.index('--') + 1:]
def covered_by(bm, bvh, p, n, skip):
    for sgn in (1, -1):
        loc, nn, idx, d = bvh.ray_cast(p + n * sgn * 0.001, -n * sgn, 0.002)
        if idx is not None and idx not in skip and bm.faces[idx].normal.dot(n) > 0.99: return idx
    return None
for nm in names:
    o = bpy.data.objects[nm]; bm = bmesh.new(); bm.from_mesh(o.data); log = []
    tag = bm.faces.layers.int.new('dup')
    for it in range(50):
        bm.faces.ensure_lookup_table(); bvh = BVHTree.FromBMesh(bm); pair = None
        for f in sorted(bm.faces, key=lambda f: f.calc_area()):
            c = f.calc_center_median(); n = f.normal
            for p in [c] + [c + (v.co - c) * 0.8 for v in f.verts]:
                g = covered_by(bm, bvh, p, n, {f.index})
                if g is not None and bm.faces[g].calc_area() >= f.calc_area(): pair = (f, bm.faces[g]); break
            if pair: break
        if not pair: break
        f, g = pair; n = g.normal; gverts = [v.co.copy() for v in g.verts]; gi = g.index
        for x in bm.faces: x[tag] = 0
        f[tag] = 1
        for i in range(len(gverts)):          # corta a face menor pelas linhas das arestas da maior
            a, b = gverts[i], gverts[(i + 1) % len(gverts)]
            pn = (b - a).cross(n).normalized()
            fs = [x for x in bm.faces if x[tag] == 1]
            geom = list({e for x in fs for e in x.edges}) + list({v for x in fs for v in x.verts}) + fs
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=a, plane_no=pn, dist=1e-6)
        bm.faces.ensure_lookup_table(); bvh = BVHTree.FromBMesh(bm)
        pieces = [x for x in bm.faces if x[tag] == 1]
        dele = [x for x in pieces if covered_by(bm, bvh, x.calc_center_median(), x.normal, {x.index} | {y.index for y in pieces}) is not None]
        log.append((len(pieces), len(dele), round(sum(x.calc_area() for x in dele), 4)))
        if not dele: break
        bmesh.ops.delete(bm, geom=dele, context='FACES')
    bm.to_mesh(o.data); o.data.update(); bm.free()
    print('DEL', nm, '(pedacos, apagados, area m2):', log, flush=True)
bpy.ops.wm.save_mainfile()
print('SALVO', bpy.data.filepath, flush=True)
