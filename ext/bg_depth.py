import sys,numpy as np,os
sys.path.insert(0,sys.argv[1])
from cci import *
root='C:/Program Files (x86)/Steam/steamapps/common/Resident Evil Biohazard HD REMASTER/nativePC'
W,H=1920,1440; near,far=10.0,10000.0; k=far/(far-near); cc=-near*far/(far-near)
out={}
for idx in range(1,40):
    p=f'{root}/arc/scr/st01/r105/r105{idx-1:02d}.arc'
    if not os.path.exists(p): continue
    d={nm:dat for nm,eh,cs,dsz,fl,dat in read_arc(p)}
    zk=[x for x in d if x.endswith('_z')]
    if not zk: continue
    z=np.frombuffer(d[zk[0]][0x14:],dtype='<f4')[:W*H].reshape(H,W)
    w=np.where((z>0)&(z<k-1e-6),cc/(z-k),0)/100.0
    out[f'c{idx}']=w[2::4,2::4].astype(np.float32)
np.savez_compressed('bg/depth.npz',**out); print(len(out))
