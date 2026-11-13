import sys,io,struct,os,numpy as np
sys.path.insert(0,sys.argv[1])
from cci import *
from PIL import Image
root='C:/Program Files (x86)/Steam/steamapps/common/Resident Evil Biohazard HD REMASTER/nativePC'
W,H=1920,1440
os.makedirs('bg',exist_ok=True)
for idx in map(int,sys.argv[2:]):
    p=f'{root}/arc/scr/st01/r105/r105{idx-1:02d}.arc'
    if not os.path.exists(p): print('missing',idx); continue
    d={nm:dat for nm,eh,cs,dsz,fl,dat in read_arc(p)}
    bk=[x for x in d if x.endswith('_000_BM_NOMIP')]
    if not bk: print('nobk',idx); continue
    raw=d[bk[0]][0x14:0x14+W*H//2]
    dds=b'DDS '+struct.pack('<7I',124,0x81007,H,W,len(raw),0,1)+b'\0'*44+struct.pack('<2I4s5I',32,4,b'DXT1',0,0,0,0,0)+struct.pack('<5I',0x1000,0,0,0,0)
    Image.open(io.BytesIO(dds+raw)).convert('RGB').save(f'bg/cam{idx:02d}.png'); print('ok',idx)
