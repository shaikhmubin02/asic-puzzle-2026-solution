"""Sanity check: extract the warm-up GDS and confirm it computes A + B == 496.

This is the only place in the puzzle where ground truth exists, so it is the
only way to know the extractor is correct before trusting it on puzzle.gds.
"""
import sys, pickle, os
import extract2
from sim import Netlist, Sim

GDS = "asic-puzzle-2026/warmup/04_final.gds"
if not os.path.exists("warmup.pkl"):
    pickle.dump(extract2.run(GDS), open("warmup.pkl", "wb"))
nl = Netlist("warmup.pkl")
print("gates",len(nl.gates),"ffs",len(nl.ffs),"ports",list(nl.ports))
def run(a,b):
    s=Sim(nl)
    s.set_port('rst_n',0); s.set_port('en',0); s.set_port('A',0); s.set_port('B',0)
    s.comb(); s.apply_async(); s.comb()
    s.set_port('rst_n',1); s.set_port('en',1)
    for i in range(7,-1,-1):
        s.set_port('A',(a>>i)&1); s.set_port('B',(b>>i)&1)
        s.step()
    s.set_port('en',0); s.comb()
    return s.get_port('S')
tests=[(248,248),(0,0),(255,241),(496&0xff,0),(200,296&0xff),(100,396&0xff),(255,255),(1,495&0xff),(240,0)]
for a,b in tests:
    print(f"a={a:3d} b={b:3d} sum={a+b:4d} S={run(a,b)}  expected={int(a+b==496)}")
ok=True
import random
for _ in range(300):
    a=random.randrange(256); b=random.randrange(256)
    r=run(a,b); e=int(a+b==496)
    if r!=e: print("MISMATCH",a,b,r,e); ok=False
print("random 300:", "ALL MATCH" if ok else "FAIL")
