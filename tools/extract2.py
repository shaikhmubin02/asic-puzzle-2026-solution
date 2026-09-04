import gdstk, collections, math, sys, pickle
S=1000.0
COND={67:0,68:1,69:2,70:3,71:4,72:5}
VIA={67:(0,1),68:(1,2),69:(2,3),70:(3,4),71:(4,5)}
def to_int_pts(p): return [(int(round(x*S)),int(round(y*S))) for x,y in p]
def manhattan_rects(pts):
    n=len(pts); ve=[]
    for i in range(n):
        x0,y0=pts[i]; x1,y1=pts[(i+1)%n]
        if x0==x1 and y0!=y1: ve.append((x0,min(y0,y1),max(y0,y1)))
    if not ve: return []
    ys=sorted({y for e in ve for y in (e[1],e[2])}); out=[]
    for a,b in zip(ys,ys[1:]):
        mid=(a+b)/2.0
        xs=sorted(e[0] for e in ve if e[1]<=mid<=e[2])
        for i in range(0,len(xs)-1,2):
            if xs[i]!=xs[i+1]: out.append((xs[i],a,xs[i+1],b))
    out.sort(key=lambda r:(r[0],r[2],r[1])); m=[]
    for r in out:
        if m and m[-1][0]==r[0] and m[-1][2]==r[2] and m[-1][3]==r[1]: m[-1]=(r[0],m[-1][1],r[2],r[3])
        else: m.append(r)
    return m
def is_rect(p):
    return len(p)==4 and ((p[0][0]==p[1][0] and p[1][1]==p[2][1] and p[2][0]==p[3][0] and p[3][1]==p[0][1]) or
                          (p[0][1]==p[1][1] and p[1][0]==p[2][0] and p[2][1]==p[3][1] and p[3][0]==p[0][0]))
def poly_rects(pts):
    ip=to_int_pts(pts); dd=[ip[0]]
    for p in ip[1:]:
        if p!=dd[-1]: dd.append(p)
    if len(dd)>1 and dd[0]==dd[-1]: dd.pop()
    if is_rect(dd):
        xs=[p[0] for p in dd]; ys=[p[1] for p in dd]
        return [(min(xs),min(ys),max(xs),max(ys))]
    return manhattan_rects(dd)

def run(gdsfile, topname=None):
    lib=gdstk.read_gds(gdsfile); byname={c.name:c for c in lib.cells}
    tops=lib.top_level()
    top = byname[topname] if topname else tops[0]
    def cell_shapes(cell):
        d=collections.defaultdict(list)
        for p in cell.polygons:
            l,dt=p.layer,p.datatype
            if dt==20 and l in COND: k=('c',COND[l])
            elif dt==44 and l in VIA: k=('v',VIA[l])
            else: continue
            d[k].extend(poly_rects(p.points))
        for pth in cell.paths:
            l,dt=pth.layers[0],pth.datatypes[0]
            if dt==20 and l in COND: k=('c',COND[l])
            elif dt==44 and l in VIA: k=('v',VIA[l])
            else: continue
            for pp in pth.to_polygons(): d[k].extend(poly_rects(pp.points))
        return dict(d)
    cellgeo={c.name:cell_shapes(c) for c in lib.cells if c is not top}
    topgeo=cell_shapes(top)
    rects=[]
    for k,rs in topgeo.items():
        for r in rs: rects.append((k,r))
    instances=[]; inst_li1=collections.defaultdict(list)
    for ref in top.references:
        cn=ref.cell.name; rot180=abs(math.degrees(ref.rotation)-180)<1e-6
        xr=bool(ref.x_reflection); ox=int(round(ref.origin[0]*S)); oy=int(round(ref.origin[1]*S))
        def f(x,y,ox=ox,oy=oy,rot180=rot180,xr=xr):
            if xr: y=-y
            if rot180: x,y=-x,-y
            return (x+ox,y+oy)
        i=len(instances); instances.append([cn,(ox,oy),rot180,xr])
        for k,rs in cellgeo[cn].items():
            for (x0,y0,x1,y1) in rs:
                a=f(x0,y0); b=f(x1,y1)
                rects.append((k,(min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))))
    parent=list(range(len(rects)))
    def find(a):
        r=a
        while parent[r]!=r: r=parent[r]
        while parent[a]!=r: parent[a],a=r,parent[a]
        return r
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: parent[rb]=ra
    B=2000; grid=collections.defaultdict(list)
    for i,(k,(x0,y0,x1,y1)) in enumerate(rects):
        for bx in range(x0//B,x1//B+1):
            for by in range(y0//B,y1//B+1): grid[(k,bx,by)].append(i)
    def ov(r1,r2): return r1[0]<=r2[2] and r2[0]<=r1[2] and r1[1]<=r2[3] and r2[1]<=r1[3]
    for (k,bx,by),idxs in grid.items():
        if k[0]!='c': continue
        for i in range(len(idxs)):
            ri=rects[idxs[i]][1]
            for j in range(i+1,len(idxs)):
                if ov(ri,rects[idxs[j]][1]): union(idxs[i],idxs[j])
    def query(k,r):
        x0,y0,x1,y1=r; seen=set(); out=[]
        for bx in range(x0//B,x1//B+1):
            for by in range(y0//B,y1//B+1):
                for i in grid.get((k,bx,by),()):
                    if i in seen: continue
                    seen.add(i)
                    if ov(r,rects[i][1]): out.append(i)
        return out
    bad=0
    for i,(k,r) in enumerate(rects):
        if k[0]!='v': continue
        lo,hi=k[1]; a=query(('c',lo),r); b=query(('c',hi),r)
        if not a or not b: bad+=1; continue
        for x in a[1:]: union(a[0],x)
        for x in b: union(a[0],x)
    def at(k,x,y):
        return [i for i in grid.get((k,x//B,y//B),())
                if rects[i][1][0]<=x<=rects[i][1][2] and rects[i][1][1]<=y<=rects[i][1][3]]
    ports={}
    for l in top.labels:
        if l.texttype!=5 or l.layer not in (68,69,70,71,72): continue
        x=int(round(l.origin[0]*S)); y=int(round(l.origin[1]*S)); li=COND[l.layer]
        h=at(('c',li),x,y)
        if not h:
            for d in range(50,401,50):
                for dx,dy in ((d,0),(-d,0),(0,d),(0,-d)):
                    h=at(('c',li),x+dx,y+dy)
                    if h: break
                if h: break
        if h: ports.setdefault(l.text,set()).add(find(h[0]))
    cells=[]
    for iidx,ref in enumerate(top.references):
        cn=ref.cell.name
        if not cn.startswith('sky130') or cn.endswith('tapvpwrvgnd_1'): continue
        _,origin,rot180,xr=instances[iidx]; ox,oy=origin
        def f(x,y,ox=ox,oy=oy,rot180=rot180,xr=xr):
            if xr: y=-y
            if rot180: x,y=-x,-y
            return (x+ox,y+oy)
        pins={}
        for l in ref.cell.labels:
            if l.texttype!=5 or l.layer!=67: continue
            px,py=f(int(round(l.origin[0]*S)),int(round(l.origin[1]*S)))
            h=at(('c',0),px,py)
            if h: pins.setdefault(l.text,set()).add(find(h[0]))
            else: print("PINMISS",cn,l.text,file=sys.stderr)
        cells.append(dict(idx=iidx,cell=cn,origin=origin,rot180=rot180,xr=xr,
                          pins={k:sorted(v) for k,v in pins.items()}))
    print(f"{gdsfile}: insts={len(instances)} rects={len(rects)} logic={len(cells)} badvias={bad}",file=sys.stderr)
    return dict(cells=cells, ports={k:sorted(v) for k,v in ports.items()}, top=top.name)

if __name__=='__main__':
    r=run(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else None)
    pickle.dump(r, open(sys.argv[3],'wb'))
    print("ports:", {k:v for k,v in r['ports'].items()}, file=sys.stderr)
