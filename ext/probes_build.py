# Light-probe grid, step 2: per probe and per light layer, fit the diffuse ambient E(n)/pi as the 9-term polynomial the
# game's character shader evaluates (Unity-style SH packing, game axes x, y-up, z):
#   S(n) = c + ax*x + ay*y + az*z + bxy*x*y + byz*y*z + bzz*z*z + bzx*z*x + cc*(x*x - y*y)
# radiance of a ray = albedo (texture mean, linear) * baked light of that layer at the hit (lightmap, linear).
# Writes captures/r105_probes.bin: i32 nx,ny,nz; f32 bx0,by0,bz0,step (blender metres); then nx*ny*nz*4*3*9 f32.
import numpy as np, pickle, os, struct
from PIL import Image
L = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers'; CAP = r'C:\Users\HENRIQUE\Tools\captures'
Z = np.load(os.path.join(L, 'probes_rays.npz')); keys = pickle.load(open(os.path.join(L, 'probes_keys.pkl'), 'rb'))
N = pickle.load(open(r'C:\Users\HENRIQUE\Tools\re1mod\ext\export_names.pkl', 'rb'))
def lin(c): c = np.asarray(c, np.float64); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
alb = np.zeros((len(keys), 3))
for i, k in keys.items():
    if k[0] == 'img' and k[1] in N and os.path.exists(os.path.join(CAP, N[k[1]])):
        a = np.asarray(Image.open(os.path.join(CAP, N[k[1]])).convert('RGB').resize((64, 64)), np.float64) / 255
        alb[i] = lin(a).mean((0, 1))
    elif k[0] == 'col': alb[i] = lin(k[1])
    else: alb[i] = 0.25
P, D, lm, key = Z['P'], Z['D'], Z['lm'], Z['key']; R = D.shape[0]
G = np.stack([D[:, 0], D[:, 2], D[:, 1]], 1)                          # ray dirs in game axes
basis = lambda n: np.stack([np.ones(len(n)), n[:, 0], n[:, 1], n[:, 2], n[:, 0] * n[:, 1], n[:, 1] * n[:, 2], n[:, 2] ** 2, n[:, 2] * n[:, 0], n[:, 0] ** 2 - n[:, 1] ** 2], 1)
B = basis(G); Bp = np.linalg.pinv(B)                                    # fit over the same directions as normals
cosw = np.maximum(G @ G.T, 0) * (4.0 / R)                               # [normal, ray]
layers = ['base', 'lareira', 'velas', 'arandelas']
out = np.zeros((len(P), 4, 3, 9), np.float32)
valid = key >= 0
for li, name in enumerate(layers):
    A = np.load(os.path.join(L, 'd_%s.npy' % name)).astype(np.float32); H = A.shape[0]
    u = np.clip((lm[..., 0] * H).astype(int), 0, H - 1); v = np.clip((lm[..., 1] * H).astype(int), 0, H - 1)
    light = A[v, u]                                                     # rows bottom-up = blender v
    rad = alb[np.maximum(key, 0)] * light * valid[..., None]            # [probe, ray, 3]
    for ch in range(3):
        E = rad[:, :, ch] @ cosw.T                                      # [probe, normal]
        out[:, li, ch, :] = (E @ Bp.T)
    print(name, 'mean ambient', float(out[:, li, :, 0].mean()))
X, Y, Zs = Z['X'], Z['Y'], Z['Z']
with open(os.path.join(CAP, 'r105_probes.bin'), 'wb') as f:
    f.write(struct.pack('<3i', len(X), len(Y), len(Zs)))
    f.write(struct.pack('<4f', X[0], Y[0], Zs[0], 0.0))
    f.write(struct.pack('<3f', X[1] - X[0], Y[1] - Y[0], Zs[1] - Zs[0]))
    f.write(out.astype('<f4').tobytes())
print('written', out.shape, 'grid', len(X), len(Y), len(Zs))
