import bpy, pickle, re, os
cap=r'C:\Users\HENRIQUE\Tools\captures'
G=pickle.load(open(r'C:\Users\HENRIQUE\Tools\re1mod\ext\export_groups.pkl','rb'))
sc=bpy.context.scene; vs=sc.view_settings.view_transform; look=sc.view_settings.look
sc.view_settings.view_transform='Standard'
fmt=sc.render.image_settings.file_format; sc.render.image_settings.file_format='PNG'; cm=sc.render.image_settings.color_mode; sc.render.image_settings.color_mode='RGBA'
names={}
for k in G:
    if k[0]!='img': continue
    img=bpy.data.images[k[1]]
    fn='r105m_'+re.sub(r'[^A-Za-z0-9_]+','_',os.path.splitext(img.name)[0])[:40]+'.png'
    try:
        img.save_render(os.path.join(cap,fn),scene=sc); names[k[1]]=fn
    except Exception as e: print('fail',img.name,e)
sc.view_settings.view_transform=vs; sc.render.image_settings.file_format=fmt; sc.render.image_settings.color_mode=cm
pickle.dump(names,open(r'C:\Users\HENRIQUE\Tools\re1mod\ext\export_names.pkl','wb'))
print(len(names))
