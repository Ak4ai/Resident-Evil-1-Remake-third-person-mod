import sys,io,struct,numpy as np
sys.path.insert(0,sys.argv[1])
from cci import *
from PIL import Image
root='C:/Program Files (x86)/Steam/steamapps/common/Resident Evil Biohazard HD REMASTER/nativePC'
W,H=1920,1440
d={nm:dat for nm,eh,cs,dsz,fl,dat in read_arc(f'{root}/arc/scr/st01/r105/r10500.arc')}
bk=[x for x in d if x.endswith('_000_BM_NOMIP')][0]
raw=d[bk][0x14:0x14+W*H//2]
dds=b'DDS '+struct.pack('<7I',124,0x81007,H,W,len(raw),0,1)+b'\0'*44+struct.pack('<2I4s5I',32,4,b'DXT1',0,0,0,0,0)+struct.pack('<5I',0x1000,0,0,0,0)
img=np.asarray(Image.open(io.BytesIO(dds+raw)).convert('RGB')).astype(np.float32)
Image.fromarray(img.astype(np.uint8)).save('bg_cam01.png')
m=np.load('door_map.npz'); U,V,M=m['U'],m['V'],m['M']
TW,TH=960,988
def up(A): return np.asarray(Image.fromarray(A.astype(np.float32)).resize((TW,TH),Image.BILINEAR))
Uu,Vu=up(U),up(V); Mu=up(M.astype(np.float32))>0.5
xo=(1-Uu/1728)*1920-0.5; yo=48+Vu-0.5      # ref is mirrored + resized from the 1920 original
x0=np.clip(np.floor(xo).astype(int),0,W-2); y0=np.clip(np.floor(yo).astype(int),0,H-2); fx=(xo-x0)[...,None]; fy=(yo-y0)[...,None]
tex=img[y0,x0]*(1-fx)*(1-fy)+img[y0,x0+1]*fx*(1-fy)+img[y0+1,x0]*(1-fx)*fy+img[y0+1,x0+1]*fx*fy
raw_tex=tex.copy()
# fill occluded texels: mirror from above the first occluded row, per column
for i in range(TW):
    col=Mu[:,i]
    if col.any():
        j0=np.argmax(col)
        for j in range(j0,TH):
            if Mu[j,i]:
                src=2*j0-j
                if src>=0: tex[j,i]=tex[src,i]
Image.fromarray(np.clip(raw_tex,0,255).astype(np.uint8)).save('door_tex_raw.png')
Image.fromarray(np.clip(tex,0,255).astype(np.uint8)).save('door_tex.png')
print('ok',Mu.mean())
