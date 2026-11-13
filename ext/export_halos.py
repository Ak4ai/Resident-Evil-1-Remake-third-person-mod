# Writes captures/r105_halos.txt for the mod (game units: x*100, z*100, y*100):
#   H x y z radius r g b intensity group   -> additive glow sprite (group: 0 base, 1 lareira, 2 velas, 3 arandelas)
#   L x y z intensity group                -> point light used for the specular highlight (table, plates, metal)
# Sources: flame / lantern / fire parts in export_groups_lm.pkl (same geometry as the RMS4).
import pickle, numpy as np
G = pickle.load(open('export_groups_lm.pkl', 'rb'))
def clusters(P, r):
    used = np.zeros(len(P), bool); out = []
    for i in range(len(P)):
        if used[i]: continue
        m = (np.linalg.norm(P - P[i], axis=1) < r) & ~used; used |= m; out.append(P[m].mean(0))
    return np.array(out)
def g(p): return (p[0] * 100, p[2] * 100, p[1] * 100)
lines = []
fl = clusters(G[('img', 'cstm_candle flame2.png')][0], 0.06)            # 28 candle flames
for p in fl: lines.append('H %.1f %.1f %.1f 16 1.0 0.72 0.42 0.55 2' % g(p + np.array([0, 0, 0.02])))
cand = clusters(fl, 0.6)                                                   # 4 candelabra
for p in cand: lines.append('L %.1f %.1f %.1f 1.0 2' % g(p + np.array([0, 0, 0.05])))
la = clusters(G[('img', 'yg_lantan01.tga')][0], 0.09)                     # chandelier bulbs
for p in la: lines.append('H %.1f %.1f %.1f 14 1.0 0.85 0.6 0.45 0' % g(p))
for p in clusters(la, 1.5): lines.append('L %.1f %.1f %.1f 0.6 0' % g(p))
fire = np.concatenate([G[k][0] for k in G if k[0] == 'img' and 'fire' in k[1].lower()])
fc = fire.mean(0); lines.append('H %.1f %.1f %.1f 55 1.0 0.55 0.25 0.5 1' % g(fc))
open(r'C:\Users\HENRIQUE\Tools\captures\r105_halos.txt', 'w').write('\n'.join(lines) + '\n')
print('flames', len(fl), 'candelabra', len(cand), 'bulbs', len(la), 'lines', len(lines))
