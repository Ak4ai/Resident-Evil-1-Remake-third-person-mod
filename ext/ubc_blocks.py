import bpy, mathutils, numpy as np
o=bpy.data.objects['Combined Mesh (root: scene) 3_14']; me=o.data; mw=o.matrix_world; R=mw.to_3x3()
P=[];B=[]
for p in me.polygons:
    n=(R@p.normal).normalized()
    if abs(n.y)<0.9: continue
    vs=[mw@me.vertices[i].co for i in p.vertices]; y=round(np.mean([v.y for v in vs]),3); xs=[v.x for v in vs]; zs=[v.z for v in vs]
    if max(zs)-min(zs)<1.0: continue
    rec=(round(min(xs),3),round(max(xs),3),y,round(min(zs),2),round(max(zs),2))
    if abs(abs(y)-6.212)<0.02 or abs(abs(y)-6.213)<0.02: P.append(rec)
    elif abs(abs(y)-6.312)<0.02: B.append(rec)
for r in sorted(set(P)): print('PIL',r)
for r in sorted(set(B)): print('BLK',r)
