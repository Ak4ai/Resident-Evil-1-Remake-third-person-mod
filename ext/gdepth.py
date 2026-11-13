import sys,json,numpy as np; sys.path.insert(0,sys.argv[1])
from cci import *
root='C:/Program Files (x86)/Steam/steamapps/common/Resident Evil Biohazard HD REMASTER/nativePC'
idx=int(sys.argv[2]); step=int(sys.argv[3])
W,H=1920,1440; near,far=10.0,10000.0; k=far/(far-near); cc=-near*far/(far-near)
d={nm:dat for nm,eh,cs,dsz,fl,dat in read_arc(f'{root}/arc/scr/st01/r105/r105{idx-1:02d}.arc')}
zk=[x for x in d if x.endswith('_z')][0]
z=np.frombuffer(d[zk][0x14:],dtype='<f4')[:W*H].reshape(H,W)
xs=np.arange(step//2,1728,step); ys=np.arange(step//2,1344,step)
out=np.zeros((len(ys),len(xs)))
for j,py in enumerate(ys):
    for i,px in enumerate(xs):
        nx=1-2*px/1728; ny=1-2*py/1344
        uo=int((nx+1)/2*W); vo=int(48+(1-ny)/2*1344)
        zz=np.median(z[vo-2:vo+3,uo-2:uo+3]); out[j,i]=cc/(zz-k)/100 if zz<k-1e-6 else 0
np.save(f'ext/gd{idx}.npy',out); print(out.shape,out.max())
