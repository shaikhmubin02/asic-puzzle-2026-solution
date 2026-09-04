import json, pickle, re, collections, sys

CDB = json.load(open('cellsdb.json'))
COMB = {'and','or','nand','nor','xor','xnor','not','buf'}
FF   = {'dffP','dffPR','dffPS','dffPSR'}

class Netlist:
    def __init__(self, pklfile):
        D = pickle.load(open(pklfile,'rb'))
        self.ports = D['ports']
        self.insts = D['cells']
        self.gates = []            # (type, out, ins)
        self.ffs   = []            # (kind, q, d, clk, rstnet)  kind dffP/dffPR/dffPS
        self.const = {}            # net -> 0/1
        self.inst_of_net = {}
        self.net_alias = {}
        vg = self.ports.get('VGND',[None])[0]; vp = self.ports.get('VPWR',[None])[0]
        self.VGND, self.VPWR = vg, vp
        localid = 0
        self.inst_gate_range = {}
        for inst in self.insts:
            base = re.sub(r'^sky130_fd_sc_hd__','',inst['cell']).rsplit('_',1)[0]
            cd = CDB[base]
            if not cd['gates']: continue
            pinmap = {k:v[0] for k,v in inst['pins'].items()}
            loc = {}
            def N(w):
                if w in pinmap: return pinmap[w]
                if w in loc: return loc[w]
                nonlocal localid
                localid += 1
                loc[w] = f"L{inst['idx']}_{w}"
                return loc[w]
            g0=len(self.gates)
            for typ,args in cd['gates']:
                if typ in COMB:
                    self.gates.append((typ, N(args[0]), [N(a) for a in args[1:]]))
                elif typ=='mux2':
                    self.gates.append(('mux2', N(args[0]), [N(a) for a in args[1:]]))
                elif typ in FF:
                    o = N(args[0]); d=N(args[1]); c=N(args[2])
                    r = N(args[3]) if len(args)>3 else None
                    self.ffs.append((typ, o, d, c, r, inst['idx']))
                elif typ=='pullup':
                    self.const[N(args[0])] = 1
                elif typ=='pulldown':
                    self.const[N(args[0])] = 0
                else:
                    raise Exception('prim '+typ)
            self.inst_gate_range[inst['idx']] = (g0, len(self.gates))
        if self.VGND is not None: self.const[self.VGND]=0
        if self.VPWR is not None: self.const[self.VPWR]=1
        # drivers
        self.driver = {}
        for i,(t,o,ins) in enumerate(self.gates): self.driver[o]=('g',i)
        for i,f in enumerate(self.ffs): self.driver[f[1]]=('f',i)
        for n in self.const: self.driver.setdefault(n,('c',n))
        self.inputs = set()
        for p,ns in self.ports.items():
            for n in ns:
                if n not in self.driver: self.inputs.add(n); self.driver[n]=('i',p)
        # topo sort comb gates
        self.order = self._topo()
    def _topo(self):
        indeg = collections.Counter(); succ=collections.defaultdict(list)
        gi_of_net = {o:i for i,(t,o,ins) in enumerate(self.gates)}
        for i,(t,o,ins) in enumerate(self.gates):
            for a in ins:
                j = gi_of_net.get(a)
                if j is not None:
                    succ[j].append(i); indeg[i]+=1
        q=[i for i in range(len(self.gates)) if indeg[i]==0]
        out=[]
        while q:
            i=q.pop(); out.append(i)
            for j in succ[i]:
                indeg[j]-=1
                if indeg[j]==0: q.append(j)
        if len(out)!=len(self.gates):
            print(f"WARNING: combinational loop, {len(self.gates)-len(out)} gates in cycles", file=sys.stderr)
            rem=[i for i in range(len(self.gates)) if i not in set(out)]
            self.loopgates=rem
            out = out + rem
        else:
            self.loopgates=[]
        return out

EV = {
 'and':  lambda v: int(all(v)),
 'or':   lambda v: int(any(v)),
 'nand': lambda v: int(not all(v)),
 'nor':  lambda v: int(not any(v)),
 'xor':  lambda v: (sum(v)&1),
 'xnor': lambda v: 1-(sum(v)&1),
 'not':  lambda v: 1-v[0],
 'buf':  lambda v: v[0],
}

class Sim:
    def __init__(self, nl):
        self.nl=nl
        self.val = collections.defaultdict(int)
        for n,v in nl.const.items(): self.val[n]=v
        self.q = {}
        for i,f in enumerate(nl.ffs): self.q[i]=0
    def comb(self):
        v=self.val; nl=self.nl
        for i,f in enumerate(nl.ffs): v[f[1]] = self.q[i]
        for n,c in nl.const.items(): v[n]=c
        for i in nl.order:
            t,o,ins = nl.gates[i]
            if t=='mux2':
                a0,a1,s = ins
                v[o] = v[a1] if v[s] else v[a0]
            else:
                v[o] = EV[t]([v[a] for a in ins])
        if nl.loopgates:
            for _ in range(30):
                ch=False
                for i in nl.loopgates:
                    t,o,ins=nl.gates[i]
                    nv = (v[ins[1]] if v[ins[2]] else v[ins[0]]) if t=='mux2' else EV[t]([v[a] for a in ins])
                    if nv!=v[o]: v[o]=nv; ch=True
                if not ch: break
    def set_port(self, name, value):
        for n in self.nl.ports[name]: self.val[n]=value
    def get_port(self, name):
        return self.val[self.nl.ports[name][0]]
    def apply_async(self):
        # async set/reset
        nl=self.nl
        for i,f in enumerate(nl.ffs):
            typ,o,d,c,r,ii = f
            if typ=='dffPR' and self.val[r]: self.q[i]=0
            elif typ=='dffPS' and self.val[r]: self.q[i]=1
    def step(self):
        """one full clock cycle: comb settle, capture D, then clock edge"""
        self.comb(); self.apply_async(); self.comb()
        nxt={}
        for i,f in enumerate(self.nl.ffs):
            typ,o,d,c,r,ii=f
            nv = self.val[d]
            if typ=='dffPR' and self.val[r]: nv=0
            if typ=='dffPS' and self.val[r]: nv=1
            nxt[i]=nv
        self.q=nxt
        self.comb()
