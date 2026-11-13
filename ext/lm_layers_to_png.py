# lm_layers/<layer>.npy (linear float16) -> captures/r105_lm_<layer>.png (gamma 2 encoded, /4) + lm_layers/scales.json
# The .npy rows are bottom-up (Blender image.pixels); PNG/D3D are top-down, so rows are flipped (export_3c writes lm v as 1-v).
# Prefers the despeckled d_<layer>.npy when it exists.
import numpy as np, json, os, sys
from PIL import Image
d=r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers'; cap=r'C:\Users\HENRIQUE\Tools\captures'
sc={}
for f in sorted(os.listdir(d)):
    if not f.endswith('.npy'): continue
    n=f[:-4]
    if n.startswith(('d_','small_','t_')) or n not in ('base','lareira','velas','arandelas'): continue
    src=os.path.join(d,'d_'+f) if os.path.exists(os.path.join(d,'d_'+f)) else os.path.join(d,f)
    a=np.flipud(np.load(src).astype(np.float32))
    s=4.0
    sc[n]=s
    Image.fromarray((np.clip(a/s,0,1)**0.5*255+.5).astype(np.uint8)).save(os.path.join(cap,f'r105_lm_{n}.png'))
    print(n,'scale',round(s,3))
json.dump(sc,open(os.path.join(d,'scales.json'),'w'),indent=1)
