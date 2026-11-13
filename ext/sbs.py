import sys
from PIL import Image, ImageDraw
ref,mod,out=sys.argv[1],sys.argv[2],sys.argv[3]
a=Image.open(ref).convert('RGB').resize((864,672));b=Image.open(mod).convert('RGB').resize((864,672))
c=Image.new('RGB',(1728+8,672+28),(30,30,30));c.paste(a,(0,28));c.paste(b,(872,28))
d=ImageDraw.Draw(c);d.text((8,6),'JOGO',fill=(255,255,0));d.text((880,6),'MODELO (Blender)',fill=(0,255,255))
c.save(out)
