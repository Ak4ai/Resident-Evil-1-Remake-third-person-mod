# Metrica do plano R105: roda DENTRO do Blender (mcp__blender__execute_blender_code ou aba Scripting).
# Erro = profundidade do modelo (raycast) - profundidade do jogo (ext/bg/depth.npz). Passa: mediana<=0.2 m e >=60% com erro<0.3 m.
import bpy, bmesh, numpy as np, mathutils, time
from mathutils.bvhtree import BVHTree
sc=bpy.context.scene; dg=bpy.context.evaluated_depsgraph_get()
t0=time.time()
bm=bmesh.new()
vl=bpy.context.view_layer
for o in [o for o in vl.objects if o.visible_get() and o.type=='MESH' and not o.hide_render]:
    ev=o.evaluated_get(dg); me=ev.to_mesh(); t=bmesh.new(); t.from_mesh(me); t.transform(o.matrix_world)
    vm={}
    for v in t.verts: vm[v.index]=bm.verts.new(v.co)
    for f in t.faces:
        try: bm.faces.new([vm[v.index] for v in f.verts])
        except ValueError: pass
    t.free(); ev.to_mesh_clear()
tree=BVHTree.FromBMesh(bm); bm.free()
DEP=dict(np.load(r'C:\Users\HENRIQUE\Tools\re1mod\ext\bg\depth.npz'))
rows=[]
# Edite CAMS para medir so algumas cameras (ex.: [8,10,26,28]); None = todas
CAMS=None
NEAR=0.5  # m; plano proximo virtual (so cam17 e cam39 mudam de nota com isso)
for i in (CAMS or range(1,40)):
    n=f'cam{i:02d}'
    if n not in bpy.data.objects or f'c{i}' not in DEP: continue
    cam=bpy.data.objects[n]; G=DEP[f'c{i}']; H,W=G.shape
    fr=[cam.matrix_world@c for c in cam.data.view_frame(scene=sc)]; tr,br,bl,tl=fr; org=cam.matrix_world.translation
    fwd=(cam.matrix_world.to_3x3()@mathutils.Vector((0,0,-1))).normalized()
    errs=[]; tot=0
    for j in range(12,348,3):
        for k in range(0,480,3):
            g=G[j,k]
            if g<=0.05: continue
            tot+=1
            py=j*4+2-48; px=(1-(k*4+2)/1920)*1728
            if not (0<=py<1344): continue
            p=bl+(br-bl)*(px/1728)+(tl-bl)*(1-py/1344); d=(p-org).normalized()
            gp=org+d*(g/d.dot(fwd))
            if abs(gp.y)>4.6 or abs(gp.x)>11.0: continue  # ponto do jogo fora da sala (porta aberta para outro comodo): nao conta
            loc,nrm,idx,dist=tree.ray_cast(org+d*NEAR,d)  # NEAR: ignora geometria colada na camera (cam17 esta dentro da lareira)
            if loc is None: continue
            errs.append(abs((loc-org).dot(fwd)-g))
    e=np.array(errs) if errs else np.array([9.0])
    rows.append((n,len(e),round(float(np.median(e)),2),round(float((e<0.3).mean()),2)))
    print(n,'mediana',rows[-1][2],'m  <0.3m:',int(rows[-1][3]*100),'%','PASSA' if rows[-1][2]<=0.2 and rows[-1][3]>=0.6 else 'falha',flush=True)
(CAMS is None) and open(r'C:\Users\HENRIQUE\Tools\re1mod\ext\cam_scores.txt','w').write('\n'.join(str(r) for r in rows))
print('total',round(time.time()-t0,1),'s')
