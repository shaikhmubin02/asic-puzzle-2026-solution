import sys, collections, pickle
from sim import Netlist, Sim
from pysat.formula import IDPool
from pysat.solvers import Cadical153

nl=Netlist('puzzle.pkl')
NCYC=121
CTR = list(range(44,49))+list(range(73,77))

# 1) get deterministic counter trajectory (independent of I) -- verify with 2 random inputs
import random
def ctr_traj(bits):
    s=Sim(nl)
    s.set_port('rst_n',0); s.set_port('enable',0); s.set_port('I',0)
    s.comb(); s.apply_async(); s.comb()
    for _ in range(3): s.step()
    s.set_port('rst_n',1); s.step(); s.step()
    s.set_port('enable',1)
    traj=[]
    for t in range(NCYC):
        traj.append(tuple(s.q[i] for i in CTR))   # state BEFORE cycle t
        s.set_port('I', bits[t]); s.step()
    traj.append(tuple(s.q[i] for i in CTR))
    return traj, s
t1,_=ctr_traj([0]*NCYC)
t2,_=ctr_traj([random.randrange(2) for _ in range(NCYC)])
t3,_=ctr_traj([1]*NCYC)
assert t1==t2==t3, "counters depend on I!"
print("counter trajectory is input-independent. OK", file=sys.stderr)
CTRVAL=t1

gi_of_net={o:i for i,(t,o,ins) in enumerate(nl.gates)}
ff_of_net={f[1]:i for i,f in enumerate(nl.ffs)}
PORT={}
for p,ns in nl.ports.items():
    for n in ns: PORT[n]=p

# check condition nets: use Q2's D at the final relevant cycle.
# Q2' = (Q2 & (~Q44|Q0)) | (~Q0 & Q44 & CHECK). We just want CHECK on the last state.
# Simpler: encode all cone FFs for NCYC cycles, then assert the CHECK expression on final state.
# CHECK from analysis:
PAIRS_neg_pos = [(32,29),(31,28),(33,35),(85,80),(84,78),(34,81),(86,79),(90,89),(91,77),(83,87),(82,88),
                 (14,19),(13,17),(15,18),(7,21),(22,8),(12,20),(9,23),(11,26),(27,30),(16,24),(25,10)]
ZEROS=[54,63,65,68,69,70,72]
ONES=[66,67,71]
# validate against Q2 expression textual form -> trust analysis; we also verify by simulation later.

pool=IDPool(); cnf=[]
TRUE=pool.id('TRUE'); cnf.append([TRUE])
def lit_const(v): return TRUE if v else -TRUE

# per-cycle net variables
netvar={}   # (net, t) -> lit
def V(net,t):
    k=(net,t)
    if k in netvar: return netvar[k]
    r=pool.id(f"n{net}_{t}"); netvar[k]=r; return r

def AND(out, ins):
    for a in ins: cnf.append([-out, a])
    cnf.append([out]+[-a for a in ins])
def OR(out, ins):
    for a in ins: cnf.append([out, -a])
    cnf.append([-out]+ins)
def XOR2(out,a,b):
    cnf.append([-out,a,b]); cnf.append([-out,-a,-b]); cnf.append([out,-a,b]); cnf.append([out,a,-b])
def EQ(out,a):
    cnf.append([-out,a]); cnf.append([out,-a])
def MUX(out,a0,a1,s):
    cnf.append([-out,-s,a1]); cnf.append([out,-s,-a1])
    cnf.append([-out,s,a0]);  cnf.append([out,s,-a0])

# input variables
Ivar=[pool.id(f"I{t}") for t in range(NCYC)]

# state literals per cycle
Q={}   # (ffidx,t) -> lit
for i in range(len(nl.ffs)):
    Q[(i,0)] = lit_const(0)
for t,c in enumerate(CTRVAL):
    for k,i in enumerate(CTR):
        Q[(i,t)] = lit_const(c[k])

# cone of FFs we need
CONE=set()
frontier=set(x for p in PAIRS_neg_pos for x in p)|set(ZEROS)|set(ONES)
while frontier:
    nf=set()
    for i in frontier:
        if i in CONE: continue
        CONE.add(i)
        f=nl.ffs[i]
        # support of D
        st=[f[2]]; seen=set()
        while st:
            n=st.pop()
            if n in seen: continue
            seen.add(n)
            if n in ff_of_net: nf.add(ff_of_net[n]); continue
            if n in nl.const or n in PORT: continue
            j=gi_of_net.get(n)
            if j is None: continue
            st.extend(nl.gates[j][2])
    frontier=nf-CONE
CONE=sorted(CONE-set(CTR))
print("cone FFs (excluding counters):",len(CONE), file=sys.stderr)

# order gates topologically once
order=nl.order
gate_needed=set()
# determine which gates are needed: those in cone of D of CONE ffs
need=set()
for i in CONE:
    st=[nl.ffs[i][2]]
    while st:
        n=st.pop()
        if n in need: continue
        need.add(n)
        if n in ff_of_net or n in nl.const or n in PORT: continue
        j=gi_of_net.get(n)
        if j is None: continue
        st.extend(nl.gates[j][2])
gates_needed=[j for j in order if nl.gates[j][1] in need]
print("gates needed per cycle:",len(gates_needed), file=sys.stderr)

def netlit(n,t):
    if n in ff_of_net:
        i=ff_of_net[n]
        return Q.get((i,t), lit_const(0))
    if n in nl.const: return lit_const(nl.const[n])
    if n in PORT:
        p=PORT[n]
        if p=='I': return Ivar[t]
        if p=='enable': return lit_const(1)
        if p=='rst_n': return lit_const(1)
        if p=='clk': return lit_const(0)
        return V(n,t)
    return V(n,t)

for t in range(NCYC):
    for j in gates_needed:
        typ,o,ins=nl.gates[j]
        ol=V(o,t)
        il=[netlit(a,t) for a in ins]
        if typ=='buf': EQ(ol,il[0])
        elif typ=='not': EQ(ol,-il[0])
        elif typ=='and': AND(ol,il)
        elif typ=='or': OR(ol,il)
        elif typ=='nand': AND(-ol,il)
        elif typ=='nor': OR(-ol,il)
        elif typ=='xor':
            cur=il[0]
            for k in range(1,len(il)):
                nx = ol if k==len(il)-1 else pool.id(f"x{j}_{t}_{k}")
                XOR2(nx,cur,il[k]); cur=nx
        elif typ=='xnor':
            cur=il[0]
            for k in range(1,len(il)):
                nx = pool.id(f"xn{j}_{t}_{k}")
                XOR2(nx,cur,il[k]); cur=nx
            EQ(ol,-cur)
        elif typ=='mux2': MUX(ol,il[0],il[1],il[2])
        else: raise Exception(typ)
    for i in CONE:
        Q[(i,t+1)] = netlit(nl.ffs[i][2], t)

# final assertions
T=NCYC
for (a,b) in PAIRS_neg_pos:
    cnf.append([-Q[(a,T)]]); cnf.append([Q[(b,T)]])
for i in ZEROS: cnf.append([-Q[(i,T)]])
for i in ONES:  cnf.append([Q[(i,T)]])

print("vars",pool.top,"clauses",len(cnf), file=sys.stderr)
s=Cadical153(bootstrap_with=cnf)
import time
t0=time.time()
r=s.solve()
print("SAT?",r,"time %.1fs"%(time.time()-t0), file=sys.stderr)
if r:
    m=set(l for l in s.get_model() if l>0)
    bits=[1 if Ivar[t] in m else 0 for t in range(NCYC)]
    print(''.join(map(str,bits)))
    pickle.dump(bits, open('solbits.pkl','wb'))
