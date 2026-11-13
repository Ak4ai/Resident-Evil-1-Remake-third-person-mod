import bpy
for o in bpy.data.objects:
    n=o.name.lower()
    if any(k in n for k in ('window','jan','glass','vidro','vitral','arch')): print('WIN',o.name[:50],o.type,o.hide_render,tuple(round(x,1) for x in o.location))
for m in bpy.data.materials:
    if any(k in m.name.lower() for k in ('window','glass','vidro','vitral','sky')): print('MAT',m.name)
for t in ('Fit_Dining','Props'):
    print('COL',t,[o.name[:30] for o in bpy.data.collections[t].all_objects if 'wind' in o.name.lower()][:5])
