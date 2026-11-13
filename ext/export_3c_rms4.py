# Writes captures/r105_lm.rms4 : 'RMS4', u32 nparts, char lightmap[64], per part: char tex[64], u32 nv, u32 nf,
# nv*(float3 pos, float2 uv, float2 lightmap uv, D3DCOLOR), nf*3*u32.
# Colour alpha 0 marks light sources (flames, lamp shades): they use the colour as light and feed the bloom mask.
# The lightmap PNG itself (captures/r105_lightmap.png) is written by Blender after the bake.
import pickle, numpy as np, struct, os
from PIL import Image
cap=r'C:\Users\HENRIQUE\Tools\captures'
LM='r105_lm_'  # prefix; mod appends base/lareira/velas/arandelas.png
G=pickle.load(open('export_groups_lm.pkl','rb')); N=pickle.load(open('export_names.pkl','rb'))
EMIS=('flame','lantan','fire'); EMIS_L=0.75
PUSH=np.load('zfight_push.npy') if os.path.exists('zfight_push.npy') else np.zeros(0,np.int64); ZOFF=0.0025  # m, along the face normal
parts=[];ci=0;tbase=0
for k,(P,UV,C,LMUV) in G.items():
    nt=len(P)//3; sel=PUSH[(PUSH>=tbase)&(PUSH<tbase+nt)]-tbase; tbase+=nt
    if k[0]=='img':
        if k[1] not in N: continue
        tex=N[k[1]]
    else:
        c=tuple(int(max(0,min(1,v))**(1/2.2)*255) for v in k[1]); tex=f'r105m_col{ci:02d}.png'; ci+=1
        Image.new('RGB',(4,4),c).save(os.path.join(cap,tex))
    if len(sel):
        P=P.copy(); t=P.reshape(-1,3,3); nn=np.cross(t[sel,1]-t[sel,0],t[sel,2]-t[sel,0]); nn/=np.maximum(np.linalg.norm(nn,axis=1,keepdims=True),1e-12)
        t[sel]+=nn[:,None,:]*ZOFF; P=t.reshape(-1,3)
    V=np.stack([P[:,0]*100,P[:,2]*100,P[:,1]*100],1).astype('<f4')
    U=np.stack([UV[:,0],1-UV[:,1]],1).astype('<f4')
    M=np.stack([LMUV[:,0],1-LMUV[:,1]],1).astype('<f4')
    emis=k[0]=='img' and any(e in k[1].lower() for e in EMIS+('paisagem',))
    b=int((0.12 if 'paisagem' in str(k[1]).lower() else EMIS_L)*255) if emis else 0
    col=np.full(len(V),((0x00 if emis else 0xFF)<<24)|(b<<16)|(b<<8)|b,dtype=np.uint32)
    T=np.arange(len(V),dtype='<u4').reshape(-1,3)
    parts.append((tex,V,U,M,col,T))
out=bytearray(b'RMS4'+struct.pack('<I',len(parts))+LM.encode().ljust(64,b'\0'))
for tex,V,U,M,col,T in parts:
    out+=tex.encode().ljust(64,b'\0')+struct.pack('<II',len(V),len(T))
    vb=np.zeros(len(V),dtype=[('p','<f4',3),('u','<f4',2),('m','<f4',2),('c','<u4')]); vb['p']=V; vb['u']=U; vb['m']=M; vb['c']=col
    out+=vb.tobytes()+T.tobytes()
open(cap+r'\r105_lm.rms4','wb').write(out)
print('parts',len(parts),'MB',round(len(out)/1e6,1))
