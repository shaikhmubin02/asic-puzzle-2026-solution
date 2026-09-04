from sim import Netlist, Sim
import pickle, random
nl=Netlist('puzzle.pkl')
def run(bits, force=None, extra=17):
    s=Sim(nl)
    s.set_port('rst_n',0); s.set_port('enable',0); s.set_port('I',0)
    s.comb(); s.apply_async(); s.comb()
    for _ in range(3): s.step()
    s.set_port('rst_n',1); s.step(); s.step()
    s.set_port('enable',1)
    for t in range(121): s.set_port('I',bits[t]); s.step()
    s.set_port('enable',0)
    if force:
        for k,v in force.items(): s.q[k]=v
        s.comb()
    out=[]
    for k in range(extra):
        s.step()
        out.append(sum(s.get_port(f'O[{j}]')<<j for j in range(8)))
    return ''.join(chr(o) for o in out if o), s
sol=pickle.load(open('solbits.pkl','rb'))
print("all zeros (0 stars) :", repr(run([0]*121)[0]))
print("all ones (121 stars):", repr(run([1]*121)[0]))
print("solution            :", repr(run(sol)[0]))
for i in range(5):
    b=[random.randrange(2) for _ in range(121)]
    print(f"random #{i} ({sum(b)} stars):", repr(run(b)[0]))
# force success on a wrong input
print("\n-- force Q1=Q2=1 with a wrong input (star count 22, invalid placement):")
b=[0]*121
for k in range(22): b[k*5]=1
print("   star count",sum(b), "->", repr(run(b)[0]))
print("   forced      ->", repr(run(b, force={1:1,2:1})[0]))
print("\n-- force Q1=1,Q2=0 / Q1=0,Q2=1 on all-zero input:")
print("   Q1=1,Q2=0:", repr(run([0]*121, force={1:1,2:0})[0]))
print("   Q1=0,Q2=1:", repr(run([0]*121, force={1:0,2:1})[0]))
print("   Q1=1,Q2=1:", repr(run([0]*121, force={1:1,2:1})[0]))
# does the solution string depend on Q36-43?
print("\n-- solution but with Q36-43 scrambled:")
for v in (0,0x5a,0xff,0x37):
    f={36+k:(v>>k)&1 for k in range(8)}
    print(f"   Q36-43={v:#04x} ->", repr(run(sol, force=f)[0]))
