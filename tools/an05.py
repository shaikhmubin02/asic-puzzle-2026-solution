from sim import Netlist
import re
nl=Netlist('puzzle.pkl')
gi={o:i for i,(t,o,ins) in enumerate(nl.gates)}
ffn={f[1]:i for i,f in enumerate(nl.ffs)}
PI={}
for p in ['I','rst_n','enable']:
    for n in nl.ports[p]: PI[n]=p
CTRA={47:'a0',48:'a1',45:'a2',46:'a3',44:'DONE'}
CTRB={74:'b0',75:'b?',76:'b?',73:'b?'}
def leaf(n):
    if n in ffn:
        i=ffn[n]
        if i in CTRA: return CTRA[i]
        if i in CTRB: return f"Q{i}"
        return f"Q{i}"
    if n in nl.const: return str(nl.const[n])
    if n in PI: return PI[n]
    return None
def ex(n,d=0,maxd=40):
    l=leaf(n)
    if l is not None: return l
    j=gi.get(n)
    if j is None: return f"?{n}"
    t,o,ins=nl.gates[j]
    if d>=maxd: return f"<{n}>"
    s=[ex(a,d+1,maxd) for a in ins]
    if t=='buf': return s[0]
    if t=='not': return f"~{s[0]}" if re.fullmatch(r'~?\w+',s[0]) else f"~({s[0]})"
    if t=='mux2': return f"({s[2]}?{s[1]}:{s[0]})"
    op={'and':'&','or':'|','xor':'^'}.get(t)
    if op: return "("+f"{op}".join(s)+")"
    if t=='nand': return "~("+"&".join(s)+")"
    if t=='nor': return "~("+"|".join(s)+")"
    if t=='xnor': return "~("+"^".join(s)+")"
for i in [54,63,62,64,50,53,55,58]+list(range(65,73)):
    typ,q,d,c,r,ii=nl.ffs[i]
    print(f"Q{i}' = {ex(d)}")
    print()
