from sim import Netlist, Sim
import collections
nl=Netlist('puzzle.pkl')
def run(bits, extra=17):
    s=Sim(nl)
    s.set_port('rst_n',0); s.set_port('enable',0); s.set_port('I',0)
    s.comb(); s.apply_async(); s.comb()
    for _ in range(3): s.step()
    s.set_port('rst_n',1); s.step(); s.step()
    s.set_port('enable',1)
    for t in range(121): s.set_port('I',bits[t]); s.step()
    s.set_port('enable',0)
    out=[]
    for k in range(extra):
        s.step(); out.append(sum(s.get_port(f'O[{j}]')<<j for j in range(8)))
    return ''.join(chr(o) for o in out if o)
res=collections.defaultdict(list)
for n in range(122):
    b=[1]*n+[0]*(121-n)
    res[run(b)].append(n)
print("distinct outputs over prefix-fill star counts 0..121:")
for k,v in res.items(): print(f"  {repr(k):25} star counts: {v if len(v)<12 else str(v[:6])+'...'+str(v[-3:])+f' ({len(v)} counts)'}")
