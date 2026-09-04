"""End-to-end: re-extract netlist straight from puzzle.gds, then replay stimulus."""
import extract2, pickle, sys
r = extract2.run("asic-puzzle-2026/puzzle.gds", "puzzle")
pickle.dump(r, open('puzzle_fresh.pkl','wb'))
from sim import Netlist, Sim
nl=Netlist('puzzle_fresh.pkl')
bits=pickle.load(open('solbits.pkl','rb'))
s=Sim(nl)
# power-on + reset
s.set_port('rst_n',0); s.set_port('enable',0); s.set_port('I',0)
s.comb(); s.apply_async(); s.comb()
for _ in range(4): s.step()
print("during reset: success =", s.get_port('success'))
s.set_port('rst_n',1)
for _ in range(2): s.step()
s.set_port('enable',1)
for t in range(121):
    s.set_port('I', bits[t]); s.step()
s.set_port('enable',0)
chars=[]
for k in range(16):
    s.step()
    o=sum(s.get_port(f'O[{j}]')<<j for j in range(8))
    chars.append(o)
    if k==0: print("first cycle after input: success =", s.get_port('success'))
print("success held high:", s.get_port('success')==1)
print("O bytes:", chars)
print("ANSWER STRING:", repr(''.join(chr(c) for c in chars if c)))
