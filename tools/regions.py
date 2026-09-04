from sim import Netlist, Sim
import pickle, sys, collections
nl=Netlist('puzzle.pkl')
GX=[(32,29),(31,28),(33,35),(85,80),(84,78),(34,81),(86,79),(90,89),(91,77),(83,87),(82,88)]
GY=[(14,19),(13,17),(15,18),(7,21),(22,8),(12,20),(9,23),(11,26),(27,30),(16,24),(25,10)]
def run(bits):
    s=Sim(nl)
    s.set_port('rst_n',0); s.set_port('enable',0); s.set_port('I',0)
    s.comb(); s.apply_async(); s.comb()
    for _ in range(3): s.step()
    s.set_port('rst_n',1); s.step(); s.step()
    s.set_port('enable',1)
    for t in range(121):
        s.set_port('I',bits[t]); s.step()
    return s
def pv(s,pairs):  # value of each pair as (msb=first?,) return tuple (a,b)
    return [(s.q[a],s.q[b]) for a,b in pairs]
# baseline: all zeros
s0=run([0]*121)
print("all-zero GX:",pv(s0,GX))
print("all-zero GY:",pv(s0,GY))
print("all-zero 65-72:",[s0.q[i] for i in range(65,73)], "Q54",s0.q[54],"Q63",s0.q[63])
print()
region=[[None]*11 for _ in range(11)]
colacc=[[None]*11 for _ in range(11)]
for r in range(11):
    for c in range(11):
        b=[0]*121; b[r*11+c]=1
        s=run(b)
        gx=pv(s,GX); gy=pv(s,GY)
        hx=[k for k in range(11) if gx[k]!=pv(s0,GX)[k]]
        hy=[k for k in range(11) if gy[k]!=pv(s0,GY)[k]]
        region[r][c]= hx[0] if len(hx)==1 else hx
        colacc[r][c]= hy[0] if len(hy)==1 else hy
print("group-X index hit per cell (=> REGION MAP):")
LET="ABCDEFGHIJK"
for r in range(11):
    print("  ", ' '.join(LET[region[r][c]] if isinstance(region[r][c],int) else '?' for c in range(11)))
print()
print("group-Y index hit per cell (=> should equal column):")
for r in range(11):
    print("  ", ' '.join(str(colacc[r][c]) if isinstance(colacc[r][c],int) else '?' for c in range(11)))
pickle.dump(dict(region=region,colacc=colacc),open('regionmap.pkl','wb'))
# region sizes
cnt=collections.Counter(region[r][c] for r in range(11) for c in range(11))
print("\nregion sizes:", dict(sorted(cnt.items())))
