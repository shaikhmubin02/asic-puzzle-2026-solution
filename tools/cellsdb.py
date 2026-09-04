import re, os, glob, json, sys

PRIMS = {'and','or','nand','nor','xor','xnor','not','buf','pullup','pulldown'}
UDP = {'sky130_fd_sc_hd__udp_dff$P':'dffP',
       'sky130_fd_sc_hd__udp_dff$PR':'dffPR',
       'sky130_fd_sc_hd__udp_dff$PS':'dffPS',
       'sky130_fd_sc_hd__udp_dff$NR':'dffNR',
       'sky130_fd_sc_hd__udp_dff$NSR':'dffNSR',
       'sky130_fd_sc_hd__udp_dff$PSR':'dffPSR',
       'sky130_fd_sc_hd__udp_mux_2to1':'mux2',
       'sky130_fd_sc_hd__udp_mux_2to1_N':'mux2N',
       'sky130_fd_sc_hd__udp_dlatch$P':'dlatchP',
       'sky130_fd_sc_hd__udp_dlatch$PR':'dlatchPR',
       }

def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    s = re.sub(r'//[^\n]*', ' ', s)
    return s

def parse_cell(path):
    txt = strip_comments(open(path).read())
    m = re.search(r'`celldefine(.*?)`endcelldefine', txt, re.S)
    body = m.group(1)
    mm = re.search(r'module\s+(\S+)\s*\((.*?)\)\s*;', body, re.S)
    name = mm.group(1)
    ports_order = [p.strip() for p in mm.group(2).split(',') if p.strip()]
    rest = body[mm.end():]
    inputs=[]; outputs=[]
    for kind, names in re.findall(r'\b(input|output|inout)\b\s+(?:wire\s+)?([^;]*);', rest):
        for n in names.split(','):
            n=n.strip()
            if not n: continue
            (inputs if kind=='input' else outputs).append(n)
    gates=[]
    # primitive/UDP instantiations:  TYPE [`UNIT_DELAY] NAME ( a , b , c );
    for gm in re.finditer(r'^\s*([A-Za-z_][\w$]*)\s*(?:`UNIT_DELAY\s*)?([A-Za-z_]\w*)\s*\(([^;]*?)\)\s*;', rest, re.M):
        typ, iname, args = gm.group(1), gm.group(2), gm.group(3)
        if typ in ('wire','input','output','inout','reg','module','endmodule','specify','assign'): continue
        args=[a.strip() for a in args.split(',') if a.strip()]
        if typ in PRIMS:
            gates.append((typ, args))
        elif typ in UDP:
            gates.append((UDP[typ], args))
        else:
            raise Exception(f"unknown prim {typ} in {path}: {gm.group(0)!r}")
    return dict(name=name, ports=ports_order, inputs=inputs, outputs=outputs, gates=gates)

if __name__=='__main__':
    used = json.load(open(sys.argv[1]))
    db={}
    for base in used:
        p=f"sky130hd/cells/{base}/sky130_fd_sc_hd__{base}.functional.v"
        if not os.path.exists(p):
            print("MISSING",base); continue
        db[base]=parse_cell(p)
    json.dump(db, open('cellsdb.json','w'), indent=1)
    for b,v in sorted(db.items()):
        print(b, "in",v['inputs'],"out",v['outputs'])
        for g in v['gates']: print("    ",g)
