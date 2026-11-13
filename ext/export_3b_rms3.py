# Writes captures/r105_luz.rms3 : 'RMS3', u32 nparts, per part: char tex[64], u32 nv, u32 nf,
# nv*(float3 pos, float2 uv, D3DCOLOR baked light), nf*3*u32. The mod shader does tex*light*2,
# so the light is stored at half scale (0.5 = unchanged texture, 1.0 = twice as bright).
# Usage: python export_3b_rms3.py [ganho]   (ganho = exposure multiplier on the baked light, default 0.33)
import pickle, numpy as np, struct, os, sys
from PIL import Image
cap=r'C:\Users\HENRIQUE\Tools\captures'
gain=float(sys.argv[1]) if len(sys.argv)>1 else 0.33
G=pickle.load(open('export_groups_luz.pkl','rb')); N=pickle.load(open('export_names.pkl','rb'))
parts=[];ci=0
EMIS=('flame','lantan','fire')
EMIS_L=0.75
for k,(P,UV,C) in G.items():
    if k[0]=='img':
        if k[1] not in N: continue
        tex=N[k[1]]
    else:
        c=tuple(int(max(0,min(1,v))**(1/2.2)*255) for v in k[1]); tex=f'r105m_col{ci:02d}.png'; ci+=1
        Image.new('RGB',(4,4),c).save(os.path.join(cap,tex))
    V=np.stack([P[:,0]*100,P[:,2]*100,P[:,1]*100],1).astype('<f4')
    U=np.stack([UV[:,0],1-UV[:,1]],1).astype('<f4')
    L=np.clip((np.clip(C,0,None)*gain)**(1/2.2)*0.5,0,1)       # display-space light, half scale
    if k[0]=='img' and any(e in k[1].lower() for e in EMIS): L[:]=EMIS_L   # light sources stay lit (flames, lamp shades)
    B=(L*255+0.5).astype(np.uint8)
    emis=k[0]=='img' and any(e in k[1].lower() for e in EMIS)
    col=((0x00 if emis else 0xFF)<<24)|(B[:,0].astype(np.uint32)<<16)|(B[:,1].astype(np.uint32)<<8)|B[:,2].astype(np.uint32)
    T=np.arange(len(V),dtype='<u4').reshape(-1,3)
    parts.append((tex,V,U,col,T))
out=bytearray(b'RMS3'+struct.pack('<I',len(parts)))
for tex,V,U,col,T in parts:
    out+=tex.encode().ljust(64,b'\0')+struct.pack('<II',len(V),len(T))
    vb=np.zeros(len(V),dtype=[('p','<f4',3),('u','<f4',2),('c','<u4')]); vb['p']=V; vb['u']=U; vb['c']=col
    out+=vb.tobytes()+T.tobytes()
open(cap+r'\r105_luz.rms3','wb').write(out)
allc=np.concatenate([p[3] for p in parts]); g=((allc>>8)&255)
print('parts',len(parts),'MB',round(len(out)/1e6,1),'luz (0-255, 128=sem mudanca) p5/p50/p95',np.percentile(g,[5,50,95]).astype(int))
