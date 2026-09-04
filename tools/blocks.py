"""Assign every standard cell to a functional block, for the die-floorplan figure.

Flops are assigned directly from the analysis. A combinational cell is assigned to
a block when every flop it feeds lives in that block; cells feeding more than one
block are 'shared'.
"""
import json, sys, collections
import gdstk
from sim import Netlist

BLOCKS = [
    ("colctr",  "Column counter",          [44, 45, 46, 47, 48]),
    ("rowctr",  "Row counter",             [73, 74, 75, 76]),
    ("colacc",  "Column accumulators",     list(range(7, 28)) + [30]),
    ("regacc",  "Region accumulators",     [28, 29, 31, 32, 33, 34, 35] + list(range(77, 92))),
    ("adj",     "Adjacency register",[49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61]),
    ("counts",  "Row / total counts", [62, 63, 64] + list(range(65, 73))),
    ("outgen",  "Output generator",        list(range(0, 7)) + list(range(36, 44))),
]
BLOCK_OF_FF = {}
for key, _, ffs in BLOCKS:
    for i in ffs:
        BLOCK_OF_FF[i] = key
assert len(BLOCK_OF_FF) == 92, len(BLOCK_OF_FF)

nl = Netlist("puzzle.pkl")
gi_of_net = {o: i for i, (t, o, ins) in enumerate(nl.gates)}
ff_of_net = {f[1]: i for i, f in enumerate(nl.ffs)}
PORT = {n for ns in nl.ports.values() for n in ns}

# gate index -> instance index
inst_of_gate = {}
for iidx, (g0, g1) in nl.inst_gate_range.items():
    for g in range(g0, g1):
        inst_of_gate[g] = iidx

# for each flop, the gates in its D cone
gate_blocks = collections.defaultdict(set)
for i, f in enumerate(nl.ffs):
    blk = BLOCK_OF_FF[i]
    seen = set()
    st = [f[2]] + ([f[4]] if f[4] else [])
    while st:
        n = st.pop()
        if n in seen:
            continue
        seen.add(n)
        if n in ff_of_net or n in nl.const or n in PORT:
            continue
        j = gi_of_net.get(n)
        if j is None:
            continue
        gate_blocks[j].add(blk)
        st.extend(nl.gates[j][2])

# gates that feed the primary outputs but no flop: the output generator's
# combinational path (O[7:0] and success are read combinationally off state)
out_cone = set()
st = [n for p, ns in nl.ports.items() if p == "success" or p.startswith("O[") for n in ns]
seen = set()
while st:
    n = st.pop()
    if n in seen:
        continue
    seen.add(n)
    if n in ff_of_net or n in nl.const:
        continue
    j = gi_of_net.get(n)
    if j is None:
        continue
    out_cone.add(j)
    st.extend(nl.gates[j][2])
for j in out_cone:
    if j not in gate_blocks:
        gate_blocks[j] = {"outgen"}

# cell widths, from the GDS cell bounding boxes
lib = gdstk.read_gds("asic-puzzle-2026/puzzle.gds")
size = {}
for c in lib.cells:
    bb = c.bounding_box()
    if bb:
        (x0, y0), (x1, y1) = bb
        size[c.name] = (x1 - x0, y1 - y0)

cells = []
counts = collections.Counter()
for inst in nl.insts:
    iidx = inst["idx"]
    name = inst["cell"]
    ox, oy = inst["origin"]
    w, h = size.get(name, (1.0, 2.72))
    # flop?
    blk = None
    for i, f in enumerate(nl.ffs):
        if f[5] == iidx:
            blk = BLOCK_OF_FF[i]
            break
    is_ff = blk is not None
    if blk is None:
        g0, g1 = nl.inst_gate_range.get(iidx, (0, 0))
        bs = set()
        for g in range(g0, g1):
            bs |= gate_blocks.get(g, set())
        if len(bs) == 1:
            blk = bs.pop()
        elif bs:
            blk = "shared"
        elif "clkbuf" in name:
            blk = "clock"
        elif g1 > g0:
            blk = "shared"
        else:
            blk = "fill"
    counts[blk] += 1
    cells.append(dict(x=round(ox / 1000.0, 3), y=round(oy / 1000.0, 3),
                      w=round(w, 3), h=round(h, 3), b=blk, f=1 if is_ff else 0))

print("cells:", len(cells), file=sys.stderr)
for k, v in counts.most_common():
    print(f"  {k:8} {v}", file=sys.stderr)

json.dump(dict(blocks=[{"key": k, "label": l, "nff": len(f)} for k, l, f in BLOCKS],
               cells=cells),
          open("floorplan.json", "w"), separators=(",", ":"))
print("wrote floorplan.json", file=sys.stderr)
