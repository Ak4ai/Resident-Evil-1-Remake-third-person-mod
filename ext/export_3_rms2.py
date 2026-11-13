import pickle,numpy as np,struct,os,shutil
from PIL import Image
cap=r'C:\Users\HENRIQUE\Tools\captures'
G=pickle.load(open('export_groups.pkl','rb')); N=pickle.load(open('export_names.pkl','rb'))
if not os.path.exists(cap+r'\r105_old_tsdf.rms2'): shutil.copy(cap+r'\r105.rms2',cap+r'\r105_old_tsdf.rms2')
parts=[];ci=0
for k,(P,UV) in G.items():
    if k[0]=='img':
        if k[1] not in N: continue
        tex=N[k[1]]
    else:
        c=tuple(int(max(0,min(1,v))**(1/2.2)*255) for v in k[1]); tex=f'r105m_col{ci:02d}.png'; ci+=1
        Image.new('RGB',(4,4),c).save(os.path.join(cap,tex))
    V=np.stack([P[:,0]*100,P[:,2]*100,P[:,1]*100],1).astype('<f4')
    U=np.stack([UV[:,0],1-UV[:,1]],1).astype('<f4')
    T=np.arange(len(V),dtype='<u4').reshape(-1,3)
    parts.append((tex,V,U,T))
out=bytearray(b'RMS2'+struct.pack('<I',len(parts)))
for tex,V,U,T in parts:
    out+=tex.encode().ljust(64,b'\0')+struct.pack('<II',len(V),len(T))
    vb=np.zeros(len(V),dtype=[('p','<f4',3),('u','<f4',2)]); vb['p']=V; vb['u']=U; out+=vb.tobytes()+T.tobytes()
open(cap+r'\r105_new.rms2','wb').write(out)
print('parts',len(parts),'MB',len(out)/1e6, 'bbox cm', np.min([p[1].min(0) for p in parts],0).round(0), np.max([p[1].max(0) for p in parts],0).round(0))