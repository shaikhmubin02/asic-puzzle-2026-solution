from sim import Netlist
import collections, sys
nl=Netlist('puzzle.pkl')
insts={c['idx']:c for c in nl.insts}
gi_of_net={o:i for i,(t,o,ins) in enumerate(nl.gates)}
ff_of_net={f[1]:i for i,f in enumerate(nl.ffs)}
PORT={}
for p,ns in nl.ports.items():
    for n in ns: PORT[n]=p
def leaf(n):
    if n in ff_of_net: return f"Q{ff_of_net[n]}"
    if n in nl.const: return str(nl.const[n])
    if n in PORT: return PORT[n]
    return None
def ex(n, depth=0, maxd=99):
    l=leaf(n)
    if l is not None: return l
    j=gi_of_net.get(n)
    if j is None: return f"?{n}"
    if depth>=maxd: return f"<net{n}>"
    t,o,ins=nl.gates[j]
    sub=[ex(a,depth+1,maxd) for a in ins]
    if t=='buf': return sub[0]
    if t=='not': return f"~{sub[0]}" if len(sub[0])<12 else f"~({sub[0]})"
    if t=='mux2': return f"({sub[2]} ? {sub[1]} : {sub[0]})"
    op={'and':'&','or':'|','xor':'^'}.get(t)
    if op: return "("+f" {op} ".join(sub)+")"
    if t=='nand': return "~("+" & ".join(sub)+")"
    if t=='nor':  return "~("+" | ".join(sub)+")"
    if t=='xnor': return "~("+" ^ ".join(sub)+")"
    raise Exception(t)
if __name__=='__main__':
    # who drives success
    sn=nl.ports['success'][0]
    print("success =", ex(sn))
    print()
    for group,label in [(range(44,49),'ctr A (44-48)'), (range(73,77),'ctr B (73-76)')]:
        print("---",label)
        for i in group:
            typ,q,d,c,r,ii=nl.ffs[i]
            print(f"  Q{i}' = {ex(d)}")
    print()
    print("--- output generator FFs 0-6,36-43")
    for i in list(range(0,7))+list(range(36,44)):
        typ,q,d,c,r,ii=nl.ffs[i]
        e=ex(d)
        print(f"  Q{i}'({typ}) = {e[:300]}")
    print()
    print("--- O bus")
    for k in range(8):
        print(f"  O[{k}] = {ex(nl.ports[f'O[{k}]'][0])[:400]}")
