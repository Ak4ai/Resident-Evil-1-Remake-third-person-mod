# Procedural night landscape seen through the dining-room windows (style: RE1 mansion grounds — dark blue sky,
# moon haze, ground fog, black tree silhouettes). Writes captures/r105m_paisagem_noite.png (2048x1024, sRGB).
import numpy as np, math, random
from PIL import Image, ImageDraw, ImageFilter
W, H = 2048, 1024; S = 2                       # supersampling for the silhouettes
rng = np.random.default_rng(7); random.seed(7)

def fbm(w, h, oct=6, base=4):
    out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(oct):
        f = base * 2 ** o
        g = rng.random((f + 1, int(f * w / h) + 1)).astype(np.float32)
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += np.asarray(im, np.float32) / 255 * amp; tot += amp; amp *= 0.5
    return out / tot

y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W)[None, :]
# sky: deep navy at the top, lighter blue-grey near the horizon
top = np.array([4, 6, 14], np.float32); hor = np.array([30, 40, 62], np.float32)
t = np.clip(y / 0.72, 0, 1) ** 1.6
sky = top * (1 - t[..., None]) + hor * t[..., None]
sky = np.broadcast_to(sky, (H, W, 3)).copy()
# moon haze (upper right) + the moon
mx, my = 0.74, 0.17
d = np.sqrt(((x - mx) * W / H) ** 2 + (y - my) ** 2)
sky += (np.exp(-d * 5.5) * 55)[..., None] * np.array([0.75, 0.85, 1.0])
sky += (np.exp(-d * 22) * 70)[..., None] * np.array([0.85, 0.9, 1.0])
moon = np.clip((0.028 - d) / 0.004, 0, 1)
sky = sky * (1 - moon[..., None]) + np.array([205, 212, 222]) * moon[..., None]
# clouds drifting over the moon
cl = fbm(W, H, 6, 3); cl = np.clip((cl - 0.52) * 3.0, 0, 1) * np.clip(1 - y / 0.6, 0, 1)
sky = sky * (1 - 0.55 * cl[..., None]) + (cl * np.exp(-d * 3) * 60)[..., None] * np.array([0.7, 0.8, 0.95])
img = Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8)).resize((W * S, H * S), Image.BICUBIC)
dr = ImageDraw.Draw(img)

def treeline(base_y, amp, rough, col, seed):
    r = np.random.default_rng(seed); n = 400
    h = np.cumsum(r.normal(0, rough, n)); h = (h - h.min()) / (np.ptp(h) + 1e-6)
    h = h * amp + r.random(n) * amp * 0.35
    pts = [(i * W * S / (n - 1), (base_y - h[i]) * S) for i in range(n)] + [(W * S, H * S), (0, H * S)]
    dr.polygon(pts, fill=col)

def tree(cx, base, height, spread, col, seed):
    r = random.Random(seed)
    def branch(x0, y0, ang, ln, w, depth):
        x1 = x0 + math.cos(ang) * ln; y1 = y0 - math.sin(ang) * ln
        dr.line([(x0 * S, y0 * S), (x1 * S, y1 * S)], fill=col, width=max(1, int(w * S)))
        if depth == 0 or ln < 6:
            for _ in range(r.randint(30, 55)):                       # leafy clump: many small irregular dabs
                rr = r.uniform(1.2, 4.5) * spread
                ox, oy = x1 + r.gauss(0, 11 * spread), y1 + r.gauss(0, 7 * spread)
                dr.ellipse([(ox - rr) * S, (oy - rr * r.uniform(0.5, 1)) * S, (ox + rr) * S, (oy + rr) * S], fill=col)
            return
        for _ in range(r.randint(2, 3)):
            branch(x1, y1, ang + r.uniform(-0.9, 0.9), ln * r.uniform(0.55, 0.85), w * 0.66, depth - 1)
    branch(cx, base, math.pi / 2 + r.uniform(-0.12, 0.12), height * r.uniform(0.25, 0.36), max(3, height / 30), 7)

# far forest (blue-grey through the fog), mid forest, garden ground
treeline(0.70 * H, 0.13 * H, 0.9, (22, 29, 44), 1)
treeline(0.76 * H, 0.10 * H, 1.2, (14, 18, 28), 2)
for i in range(14):
    tree(random.uniform(0, W), 0.80 * H, random.uniform(170, 260), 1.0, (11, 14, 22), 100 + i)
dr.rectangle([0, int(0.80 * H * S), W * S, H * S], fill=(9, 11, 16))
img = img.resize((W, H), Image.LANCZOS)
a = np.asarray(img, np.float32)
# ground fog banks (lighter, bluish) and a soft moonlight wash
fog = fbm(W, H, 5, 2) * np.exp(-((y - 0.79) / 0.07) ** 2)
a += (fog * 70)[..., None] * np.array([0.62, 0.72, 0.9])
fog2 = fbm(W, H, 4, 3) * np.exp(-((y - 0.93) / 0.08) ** 2)
a += (fog2 * 45)[..., None] * np.array([0.6, 0.7, 0.85])
img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
dr = ImageDraw.Draw(img, 'RGBA')
# near trees framing the view (pure black, with a faint moon rim)
img2 = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); dr2 = ImageDraw.Draw(img2)
dr_save = dr; dr = dr2
for i, cx in enumerate((120, 700, 1350, 1900)):
    tree(cx + random.uniform(-80, 80), 1.02 * H, random.uniform(620, 820), 1.6, (3, 4, 7, 255), 500 + i)
img2 = img2.resize((W, H), Image.LANCZOS)
rim = img2.split()[3].filter(ImageFilter.GaussianBlur(3))
glow = Image.new('RGBA', (W, H), (60, 75, 100, 0)); glow.putalpha(rim.point(lambda v: int(v * 0.25)))
img = Image.alpha_composite(img.convert('RGBA'), glow); img = Image.alpha_composite(img, img2).convert('RGB')
img = img.filter(ImageFilter.GaussianBlur(0.6))
img.save(r'C:\Users\HENRIQUE\Tools\captures\r105m_paisagem_noite.png')
img.save(r'C:\Users\HENRIQUE\Tools\re1mod\preview\paisagem_noite.png')
print('ok', img.size)
