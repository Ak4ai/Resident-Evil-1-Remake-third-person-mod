# Same as export_1_groups_blender.py, but also collects the baked light (color attribute 'luz', corner domain)
# so export_3b_rms3.py can write RMS3 (pos, uv, baked colour). Run inside Blender on r105_bake.blend.
import bpy, numpy as np, re, pickle
dg=bpy.context.evaluated_depsgraph_get()
def base_image(m):
    if not m or not m.use_nodes: return None
    nt=m.node_tree; b=next((n for n in nt.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if b and b.inputs['Base Color'].is_linked:
        n=b.inputs['Base Color'].links[0].from_node
        for _ in range(4):
            if n.type=='TEX_IMAGE': return n.image
            ins=[i for i in n.inputs if i.is_linked]
            if not ins: break
            n=ins[0].links[0].from_node
    t=[n for n in nt.nodes if n.type=='TEX_IMAGE' and n.image]
    pref=[n for n in t if re.search(r'(_bm|albd|diff|color|col)',n.image.name,re.I)]
    return (pref or t or [None])[0].image if (pref or t) else None
def base_color(m):
    if m and m.use_nodes:
        b=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if b: return tuple(b.inputs['Base Color'].default_value[:3])
    return tuple(m.diffuse_color[:3]) if m else (0.5,0.5,0.5)
groups={}
objs=[o for c in ('Fit_Dining','Props') for o in bpy.data.collections[c].all_objects if o is not None and o.type in ('MESH','CURVE') and not o.hide_render]
for o in objs:
    ev=o.evaluated_get(dg); me=ev.to_mesh()
    if me is None or not len(me.polygons): ev.to_mesh_clear(); continue
    me.calc_loop_triangles(); mw=np.array(o.matrix_world)
    co=np.array([v.co[:] for v in me.vertices]); W=(mw[:3,:3]@co.T).T+mw[:3,3]
    uvl=me.uv_layers.active
    uvs=np.array([d.uv[:] for d in uvl.data]) if uvl else np.zeros((len(me.loops),2))
    ca=me.color_attributes.get('luz')
    if ca and ca.domain=='CORNER': col=np.array([d.color[:3] for d in ca.data])
    elif ca and ca.domain=='POINT':
        pc=np.array([d.color[:3] for d in ca.data]); col=pc[[l.vertex_index for l in me.loops]]
    else: col=np.ones((len(me.loops),3))
    for t in me.loop_triangles:
        m=o.material_slots[t.material_index].material if t.material_index<len(o.material_slots) else None
        img=base_image(m)
        key=('img',img.name) if img else ('col',tuple(round(c,3) for c in base_color(m)))
        g=groups.setdefault(key,[[],[],[]])
        for li,vi in zip(t.loops,t.vertices): g[0].append(W[vi]); g[1].append(uvs[li]); g[2].append(col[li])
    ev.to_mesh_clear()
print('groups',len(groups),'tris',sum(len(g[0])//3 for g in groups.values()))
pickle.dump({k:(np.array(v[0],np.float32),np.array(v[1],np.float32),np.array(v[2],np.float32)) for k,v in groups.items()},
            open(r'C:\Users\HENRIQUE\Tools\re1mod\ext\export_groups_luz.pkl','wb'))
