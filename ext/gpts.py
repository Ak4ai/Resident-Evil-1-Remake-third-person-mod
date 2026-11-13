import sys,json,numpy as np; sys.path.insert(0,sys.argv[1])
from cci import *
root='C:/Program Files (x86)/Steam/steamapps/common/Resident Evil Biohazard HD REMASTER/nativePC'
idx=int(sys.argv[2]); step=int(sys.argv[3])
cams=json.load(open('../out/r105_refs/cams.json')); c=[x for x in cams if x['idx']==idx][0]
W,H=1920,1440; near,far=10.0,10000.0; k=far/(far-near); cc=-near*far/(far-near)
d={nm:dat for nm,eh,cs,dsz,fl,dat in read_arc(f'{root}/arc/scr/st01/r105/r105{idx-1:02d}.arc')}
z=np.frombuffer(d[[x for x in d if x.endswith('_z')][0]][0x14:],dtype='<f4')[:W*H].reshape(H,W)
pos=np.array(c['pos']);tgt=np.array(c['tgt']);f=tgt-pos;f/=np.linalg.norm(f);r=np.cross(f,[0,1,0]);r/=np.linalg.norm(r);u=np.cross(r,f)
sy=1/np.tan(np.radians(c['fov'])/2)*(1344/1440);sx=sy/1.2
P=[]
for py in range(step//2,1344,step):
    for px in range(step//2,1728,step):
        nx=1-2*px/1728; ny=1-2*py/1344; uo=int((nx+1)/2*W); vo=int(48+(1-ny)/2*1344)
        zz=z[vo,uo]
        if zz>=k-1e-6 or zz<=0: continue
        w=cc/(zz-k); p=pos+w*(nx/sx*r+ny/sy*u+f); P.append((px,py,p[0]/100,p[2]/100,p[1]/100))
np.save(f'gp{idx}.npy',np.array(P)); print(len(P))
