"""Capture the signal trace around the input/output boundary, for the waveform figure."""
import json, pickle, sys
from sim import Netlist, Sim

nl = Netlist("puzzle.pkl")
bits = pickle.load(open("solbits.pkl", "rb"))

s = Sim(nl)
s.set_port("rst_n", 0); s.set_port("enable", 0); s.set_port("I", 0)
s.comb(); s.apply_async(); s.comb()
for _ in range(3):
    s.step()
s.set_port("rst_n", 1); s.step(); s.step()
s.set_port("enable", 1)

TAIL = 3          # last input cycles to show
SHOW_OUT = 16     # output cycles to show
rows = []
for t in range(121):
    s.set_port("I", bits[t]); s.step()
    if t >= 121 - TAIL:
        rows.append(dict(lbl=f"{t + 1}", en=1, i=bits[t],
                         succ=s.get_port("success"),
                         o=sum(s.get_port(f"O[{j}]") << j for j in range(8))))
s.set_port("enable", 0)
for k in range(SHOW_OUT):
    s.step()
    rows.append(dict(lbl=f"+{k + 1}", en=0, i=0,
                     succ=s.get_port("success"),
                     o=sum(s.get_port(f"O[{j}]") << j for j in range(8))))

for r in rows:
    r["ch"] = chr(r["o"]) if 32 <= r["o"] < 127 else ""
json.dump(dict(rows=rows, tail=TAIL), open("wavedata.json", "w"), separators=(",", ":"))
print("cycles:", len(rows), file=sys.stderr)
print("string:", "".join(r["ch"] for r in rows), file=sys.stderr)
print("success rises at:", next(i for i, r in enumerate(rows) if r["succ"]), file=sys.stderr)
