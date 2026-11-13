# Finds overlapping near-coplanar triangles (z-fighting) in the exported RMS4 geometry (export_groups_lm.pkl).
import pickle, numpy as np, collections, sys
G=pickle.load(open('export_groups_lm.pkl','rb')); N=pickle.load(open('export_names.pkl','rb'))
T=[];gid=[];names=[]
for gi,(k,(P,UV,C,M)) in enumerate(G.items()):
    names.append(N.get(k[1],str(k[1])) if k[0]=='img' else 'col'+str(k[1]))
    t=P.reshape(-1,3,3); T.append(t); gid.append(np.full(len(t),gi))
T=np.concatenate(T).astype(np.float64); gid=np.concatenate(gid)
c=T.mean(1); n=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]); a=np.linalg.norm(n,axis=1); ok=a>1e-9; n[ok]/=a[ok,None]
d=(n*c).sum(1)
def inside(p,t,nn):
    e=[np.cross(t[(k+1)%3]-t[k],p-t[k])@nn for k in range(3)]
    return all(x>=-1e-6 for x in e) or all(x<=1e-6 for x in e)
cell=np.floor(c/0.08).astype(int)
H=collections.defaultdict(list)
for i in np.where(ok&(a/2>2e-6))[0]: H[tuple(cell[i])].append(i)
hits=collections.Counter(); loc=collections.defaultdict(list); bad=set(); push=set(); PAIRS=[]
offs=[(x,y,z) for x in (-1,0,1) for y in (-1,0,1) for z in (-1,0,1)]
for key,idx in H.items():
    cand=[j for o in offs for j in H.get((key[0]+o[0],key[1]+o[1],key[2]+o[2]),())]
    cand=np.array(cand)
    for i in idx:
        nn=n[cand]; dot=nn@n[i]
        m=(np.abs(dot)>0.995)&(cand!=i)
        js=cand[m]
        if not len(js): continue
        gap=np.abs((T[js].mean(1)-c[i])@n[i])
        js=js[gap<0.004]
        for j in js:
            if j<i: continue
            if inside(c[i]-n[i]*((c[i]-T[j][0])@n[i]),T[j],n[i]) or inside(c[j]-n[i]*((c[j]-T[i][0])@n[i]),T[i],n[i]):
                k=tuple(sorted((names[gid[i]],names[gid[j]]))); hits[k]+=1; loc[k].append(c[i]); bad.add(i); bad.add(j); push.add(i if a[i]<a[j] else j); PAIRS.append((i,j,float(n[i]@n[j])))
print('overlapping pairs',sum(hits.values()),'tris',len(bad))
for k,v in hits.most_common(30):
    L=np.array(loc[k]); print(v,k,'median',np.round(np.median(L,0),2),'spread',np.round(L.std(0),2))
np.save('zfight_tris.npy',np.array(sorted(bad)))
np.save('zfight_centroids.npy',c[np.array(sorted(bad))] if bad else np.zeros((0,3)))
# push whole connected sheets, never single triangles (a lone pushed triangle opens a crack in its own surface)
key=np.round(T*2000).astype(np.int64)                    # 0.5 mm grid
parent=np.arange(len(T))
def find(x):
    while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
    return x
vmap={}
for i in range(len(T)):
    for k in range(3):
        kk=(int(gid[i]),)+tuple(key[i,k])
        j=vmap.setdefault(kk,i)
        if j!=i:
            ri,rj=find(i),find(j)
            if ri!=rj: parent[ri]=rj
root=np.array([find(i) for i in range(len(T))])
area=collections.Counter()
for i in range(len(T)): area[root[i]]+=a[i]/2
comp_push=set(); skipped=0; back2back=0
for i,j,dd in PAIRS:
    ri,rj=root[i],root[j]
    if ri==rj: skipped+=1; continue
    fi='fabric' in names[gid[i]].lower(); fj='fabric' in names[gid[j]].lower()
    if fi!=fj: comp_push.add(ri if fi else rj); continue          # upholstery always in front of the frame panel under it
    if dd<0: comp_push.add(ri); comp_push.add(rj); back2back+=1   # double-sided duplicate: both move out along their own normal
    else: comp_push.add(ri if area[ri]<area[rj] else rj)          # decal over a surface: the smaller sheet comes forward
print('back-to-back pairs',back2back)
print('self-overlap pairs skipped',skipped)
sel=np.where(np.isin(root,np.array(sorted(comp_push))))[0] if comp_push else np.zeros(0,np.int64)
np.save('zfight_push.npy',np.array(sorted(sel),dtype=np.int64)); print('push tris',len(push),'-> sheets',len(comp_push),'tris moved',len(sel))
