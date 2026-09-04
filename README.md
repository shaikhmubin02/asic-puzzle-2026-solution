# Reverse-engineering the Jane Street ASIC puzzle

By Mubin Shaikh - [blog post](https://mubin.page/ui/reverse-engineering-an-asic)

**Answer: `(* TWO STARS *)`**

The chip is an 11x11 Star Battle ("Two Not Touching") puzzle checker. Feed it the
unique solution as 121 serial bits and `success` goes high; the output generator then
clocks that string out on `O[7:0]`.

```
0000000101010000100000000000010101010000000000001010000001000001000000100000101000010000000100000010000010010001010000000
```

Everything below is how I got there. All the tooling is in `tools/`.

---

## Starting out

The repo gives you `puzzle.gds`, a labelled `layout.png`, an `example_inputs.vcd`
with a deliberately wrong stimulus, and a warm-up directory containing a tiny
`A + B == 496` design at every stage of the flow: Verilog source, synthesized
netlist, DEF, and final GDS.

That warm-up directory is the most useful thing in the repo, and not because the
design is interesting. It's the only place where you have ground truth. If your
extractor can turn `warmup/04_final.gds` back into something that computes
`A + B == 496`, you can trust it on the real chip. If it can't, you'd never know
what you were looking at. I decided upfront that I wouldn't touch `puzzle.gds`
until the warm-up round-tripped.

## The GDS is friendlier than it looks

First thing I did was dump the cell hierarchy. Eighty-one cells, one top level cell
named `puzzle`, and then this:

```
sky130_fd_sc_hd__nand2_2
sky130_fd_sc_hd__dfrtp_2
sky130_fd_sc_hd__a221o_2
sky130_fd_sc_hd__mux2_1
...
```

The standard cells kept their names. Not just their names. Dumping the labels
inside `sky130_fd_sc_hd__nand2_2` gives you `A`, `B`, `Y`, `VPWR`, `VGND` sitting on
the li1 label layer (67/5), exactly where the pins are. The README says "many
internal names removed", and what got removed was the top-level net names. The
library is intact.

That changes the problem completely. I don't have to identify gates from transistor
geometry. I know what every cell is and where its pins are. All I have to do is
figure out which pins are electrically connected. That's a connectivity extraction,
which is tedious but completely mechanical.

Two other things I checked before writing any real code, because both would have
cost me hours later:

- Every reference has magnification 1, rotation of only 0 or 180 degrees, optional
  Y-mirror, and no array repetitions. So the transform math is four lines.
- Every polygon in the top cell has exactly four vertices. All 1499 of them. The
  router emitted pure rectangles. Inside the standard cells there are L-shapes, but
  the top level, which is where all the interesting routing lives, is rectangles
  all the way down.

## Turning rectangles into nets

The extractor (`tools/extract2.py`) is about 120 lines and does this:

1. **Decompose everything into rectangles.** All the geometry is Manhattan, so a
   scanline band decomposition is exact: collect the distinct Y coordinates of the
   vertical edges, and for each horizontal band, sort the vertical edges crossing it
   and pair them off even-odd. Rectangles in, rectangles out; L-shapes and
   staircases come out as a few stacked rectangles. GDS `PATH` records get converted
   with `to_polygons()` first.
2. **Flatten.** Walk the top cell's references, transform each cell's local
   rectangles into absolute nanometre coordinates.
3. **Merge per layer.** Union-find over rectangles that touch or overlap on the same
   layer, using closed intervals so edge-abutting shapes count as connected. I
   bucket everything into a 2 um grid first, so I'm not doing 92,000 squared
   comparisons.
4. **Stitch the layers.** For each via shape, find the metal it overlaps on the
   layer below and above and union all of it together. The via layers in sky130 are
   mcon 67/44 (li1 to met1), via 68/44, via2 69/44, via3 70/44, via4 71/44.
5. **Attach names.** Transform each instance's li1 pin labels into absolute
   coordinates and look up which net contains that point. Same for the top-level
   70/5 labels, which give you `clk`, `rst_n`, `enable`, `I`, `success`, `O[0..7]`.

The number I watched most closely was unconnected vias. A via that doesn't land on
metal on both sides means my layer map is wrong, or my rectangle decomposition
dropped something, or I'd fumbled a transform. It went from a few hundred to zero as
I fixed things, and once it hit zero everything else fell into place: 92,001
rectangles, 942 logic cells, 92 flip-flops, 741 signal nets. And the other check I
cared about: every single cell pin resolved to exactly one net. Zero pins on two
nets means I never accidentally shorted anything together.

For gate behaviour I didn't want to rely on remembering what `a21boi` does. SkyWater
ships functional Verilog for every cell, and it's all structural primitives:

```verilog
nand nand0 (nand0_out  , A2, A1         );
nand nand1 (nand1_out_X, B1_N, nand0_out);
buf  buf0  (X          , nand1_out_X    );
```

So `tools/cellsdb.py` clones the PDK library and parses those into primitive gate
lists: `and`, `or`, `nand`, `nor`, `xor`, `xnor`, `not`, `buf`, `udp_dff$P/$PR/$PS`,
`udp_mux_2to1`, `pullup`, `pulldown`. The semantics are the vendor's, not mine.

Then the warm-up test. Extract `warmup/04_final.gds`, levelize the combinational
logic, simulate 8 clocks of shifting followed by a comparison, and check `S` against
`A + B == 496` on 300 random pairs. All 300 matched. Time to look at the real thing.

## Ninety-two flip-flops

`puzzle.gds` came out to 942 cells and 1794 primitive gates. `success` traces
straight back to a single flop through one buffer, so the whole question is what
sets that flop.

Rather than read 1794 gates, I computed, for each flop, the set of other flops in its
D input's combinational support, and printed that sorted by physical position. The
structure jumps out immediately:

```
 ff type          x       y   #g  Dsupport(ffs)                 ports
 47 dffPR     26220  152320   15  [44, 45, 46, 47, 48]          ['enable']
 46 dffPR     28980  157760   20  [44, 45, 46, 47, 48]          ['enable']
 48 dffPR     30820  146880   19  [44, 45, 46, 47, 48]          ['enable']
 ...
 12 dffPR    115920  255680   21  [12, 20, 44, ...]             ['I','enable']
 20 dffPR    113620  261120   18  [12, 20, 44, ...]             ['I','enable']
 ...
 34 dffPR    114080  125120  387  [34, 44, ..., 73, 74, 75, 76] ['I','enable']
```

Flops 44-48 depend only on themselves and `enable`. That is a counter. 73-76 do
the same, but gated by 44-48, a second counter that ticks when the first one
wraps. Then a long list of flops that come in **pairs**: 12 depends on 12 and
20, 20 depends on 12 and 20, and so on. And a set of flops with ~385-gate input
cones that all reference the second counter.

Expanding `success`'s driver into a boolean expression was the moment the shape of
the thing became clear:

```
Q2' = (Q2 & (~Q44|Q0))
    | (~Q0 & Q44
       & (~Q32 & Q29) & (~Q31 & Q28) & (Q35 & ~Q33)
       & (~Q85 & Q80) & (Q78 & ~Q84) & (~Q34 & Q81) & (~Q86 & Q79)
       & (Q89 & ~Q90) & (~Q91 & Q77) & (~Q83 & Q87) & (Q88 & ~Q82)
       & (~Q14 & Q19) & (~Q13 & Q17) & (Q18 & ~Q15)
       & (~Q7  & Q21) & (Q8  & ~Q22) & (~Q12 & Q20) & (~Q9 & Q23)
       & (Q26 & ~Q11) & (~Q27 & Q30) & (~Q16 & Q24) & (Q10 & ~Q25)
       & ~Q54 & ~Q63
       & (Q67 & Q66 & Q71 & ~(Q65|Q68|Q69|Q70|Q72)))
```

Twenty-two two-flop pairs, each of which has to end up holding one specific
two-bit value. Two sticky flags that have to be clear. And eight flops that have to
hold one specific pattern.

Simulating the counters told me `enable` is held high for exactly **121** cycles,
and 121 = 11 x 11. Eleven pairs in one group, eleven in the other. At that point I
was fairly confident it was a grid constraint puzzle with per-row and per-column
counts, and I guessed N-queens.

## The chip tells you what it is

Before chasing that, I ran the all-zeros input through the simulator just to see what
came out of the output generator. `O[7:0]` clocked out:

```
69 77 80 84 89 32 83 75 89   ->   "EMPTY SKY"
```

Which was a great feeling for two reasons. First, it's a full-loop confirmation that
the extraction is right: nine bytes of clean English don't fall out of a netlist you
got wrong. Second, "EMPTY SKY" is a hint about the domain.

I'd also noticed by then that the provided VCD spells `TRY AGAIN` on `O`, so the
generator clearly has multiple messages in it.

So I went back to the flop pairs. Probing the extracted netlist one cell at a time,
placing a single star at cell (r, c) to see which pair's accumulator ticks, the second
group turned out to depend only on the column, so those eleven pairs are column
counters. And the required value works out to 2 rather than 1, which killed the
N-queens theory. The confirmation arrived when I fed in a SAT solution and the chip
printed:

```
(* TWO STARS *)
```

Two stars per row, two per column, and the "no two stars touch" rule that had been
sitting in front of me the whole time as a twelve-stage shift register. It's a
Star Battle. And the answer string is an OCaml comment, which is a nice touch for
Jane Street.

## What the checkers actually are

Once you know the game, every block has an obvious job.

Two counters give you the coordinates. `ctrA` (bits Q47, Q48, Q45, Q46) counts 0-10
and wraps: that's the column. `ctrB` (Q73-Q76) ticks on each wrap: that's the row.
Q44 is a sticky "input phase done" that sets after the 121st bit. Neither counter
depends on `I`, which matters later.

**Column counts.** Eleven two-bit accumulators, each enabled when `ctrA` equals its
index. Each must end at 2.

**Region counts.** Eleven more two-bit accumulators. These are the flops with the
~385-gate cones, because their enable has to decode the region from the row and
column together. Each must end at 2.

**Row count.** One two-bit counter with a sticky error flag, checked at `ctrA == 10`,
i.e. the end of every row.

**Adjacency.** This is the prettiest part of the design. A twelve-stage shift
register holds the last twelve input bits:

```
Q50 -> Q60 -> Q52 -> Q59 -> Q51 -> Q56 -> Q49 -> Q61 -> Q57 -> Q58 -> Q55 -> Q53
```

Since a row is eleven cells, the taps land on exactly the neighbours you care about.
At time `t`, `Q50` is `t-1` (the cell to the left), `Q58` is `t-10` (up and right),
`Q55` is `t-11` (directly above), and `Q53` is `t-12` (up and left). The error flag
fires if a star lands next to any of those four:

```
Q54' = ( ((a2|a0|~(a1&a3)) & Q58)          // up-right, suppressed at col 10
         | Q55                              // above, always
         | ((a3|a2|a1|a0) & Q50)            // left, suppressed at col 0
         | ((a3|a2|a1|a0) & Q53)            // up-left, suppressed at col 0
       ) & I & active | Q54
```

The `ctrA` terms are just edge-of-row guards so column 0 doesn't wrap around to
column 10 of the previous row. Checking only the four already-seen neighbours is
enough by symmetry: every adjacent pair gets caught exactly once, when the later of
the two arrives. That's "no two stars touch, even diagonally", in about a dozen
gates plus a shift register.

**Total count.** An eight-bit ripple counter (b0 through b7 are Q68, Q67, Q66, Q65,
Q71, Q70, Q72, Q69) that has to read exactly 22. It's redundant given the row
checks, but it's what the output generator uses to pick its message.

`success` is registered on the single cycle where `Q44 & ~Q0`, one cycle after the
last input bit, and then latches.

## Reading the puzzle off the silicon

The region map isn't stored anywhere as data. It's baked into the decode logic for
those eleven region accumulators. Rather than untangle 385 gates eleven times, I
probed it: place exactly one star at each of the 121 cells in turn, and record which
region accumulator moves. Eleven runs of 121 simulations, and out comes the map.

Here it is, with the solution marked:

```
+---+---+---+---+---+---+---+---+---+---+---+
|                   |       | * |     * |   |
+   +   +---+   +   +   +---+   +   +   +   +
| *     |   |       | * |       |       |   |
+   +   +   +---+---+   +---+   +---+   +   +
|       |   |               | *     | * |   |
+   +   +   +   +---+---+---+---+   +---+   +
| *     | * |   |           |   |       |   |
+---+   +   +   +   +---+---+   +---+---+   +
|   |   |   |   | * |     *                 |
+   +---+   +   +   +---+---+   +---+---+---+
|         * |   |           |   | *         |
+---+---+---+   +---+---+   +   +   +---+---+
|                 *     |   |   |   |     * |
+   +---+---+---+---+---+   +   +   +   +   +
|   | *         |         * |   |   |       |
+   +   +   +---+---+---+---+   +   +   +   +
|   |       | * |               |   |     * |
+   +---+   +   +---+   +   +   +   +---+---+
|       |   |       | *         | *         |
+   +---+   +   +---+   +   +   +---+---+---+
|   | *     | * |                           |
+---+---+---+---+---+---+---+---+---+---+---+
```

I checked that every region is orthogonally connected, which they are. The sizes are
4, 5, 6, 7, 8, 8, 9, 11, 14, 21 and 28, much more irregular than a typical
hand-made Star Battle, but the puzzle is well formed and the solution is unique, so
it does its job.

## Letting a SAT solver do the puzzle

I never solved the Star Battle by hand. Once you have a gate-level netlist, you
don't have to understand the puzzle to solve it. You just have to compile the
circuit into CNF and ask for an input that makes `success` true.

The one thing that makes this cheap is that the counters don't depend on `I`. I
verified that by simulating the counter trajectory with all-zeros, all-ones, and a
random input and asserting the three traces are identical. So I can constant-fold
`ctrA`, `ctrB` and the phase signals at every cycle, which strips a lot of logic out
of the unrolled formula.

After that it's a standard bounded unrolling. The `success` cone is 68 flops and 897
gates per cycle; unroll 121 cycles with Tseitin encoding, initialize all the flops to
zero (they're all `dffPR`, so reset clears them; the only reset-less flops on the
die are in the output generator), tie `enable` and `rst_n` high, leave `I` free, and
assert the final check. That's 110k variables and 297k clauses.

CaDiCaL solved it in under 0.1 seconds. Then I added a blocking clause and asked
again, and it came back UNSAT: **the solution is unique.**

Which matters more than it sounds like, because of the next bit.

## The part I liked most

The output generator is an eight-bit nonlinear state register plus a four-bit
character counter, and `O` is a four-way select. I found the selector conditions by
expanding `O[0]` symbolically and spotting that the mux terms decode the total star
counter being 0 and being 121:

| Condition | Output |
| --- | --- |
| 0 stars | `EMPTY SKY` |
| 121 stars | `BIG BANG` |
| `success` | the answer |
| otherwise | `TRY AGAIN` |

The three easter-egg branches are plain ROM. The winning branch is ROM **XOR** the
eight-bit state register, and that register spends the whole input phase absorbing
`I`. So it's a tiny keystream derived from your input.

I tested this by holding the input fixed and scrambling those eight flops, and got:

```
'M\xad\xf3\x83\x13y\x1c\xf9yc\xa2h\x93\xb1\x8f'
```

Which is the point. You cannot force `success` high, or patch the netlist, or guess
at the string. If the 121 bits you shifted in aren't exactly right, the keystream is
wrong and the answer decodes to noise. The only way to read `(* TWO STARS *)` off the
chip is to actually solve the puzzle. That's a genuinely elegant piece of puzzle
design, and I appreciated it more the longer I looked at it.

## Easter eggs

Six of them:

- **`EMPTY SKY`**: feed an all-zero grid.
- **`BIG BANG`**: feed an all-ones grid, all 121 cells. These two, plus the default
  `TRY AGAIN` and the winning message, are the four branches of the output mux,
  selected by the total-star counter and the success flag.
- **`The night sky awaits`**: hidden in `example_inputs.vcd`. Its 242 stimulus bits
  are two 121-bit attempts. Take each grid row's first seven bits as an LSB-first
  7-bit ASCII character, and the 22 rows spell it out. It's also why columns 7
  through 10 are conspicuously empty in that stimulus, which is what made me look.
- The VCD's `$version` field: *"Leave no stone unturned! But for this file, consider
  looking at it in a waveform viewer instead."*
- The VCD's `$date` field: `Sat Dec 31 23:59:60 2016`, second 60, which was a real
  leap second.
- `(* TWO STARS *)` is an OCaml comment.

I also went looking for hidden geometry in the layout and didn't find any. Every
top-level polygon is a four-vertex rectangle, the only non-routing layers are the
place-and-route boundary and some filler cells whose names were stripped to
`INTERNAL_3` and `INTERNAL_7`, and there's no text drawn in metal.

## Tools

No commercial EDA, no Magic or KLayout extraction: just `gdstk` for parsing,
`python-sat` (CaDiCaL 1.5.3) for the solve, and the SkyWater functional Verilog for
cell semantics.

| File | What it does |
| --- | --- |
| `tools/extract2.py` | GDS to netlist: rectangle decomposition, union-find, via stitching, pin mapping |
| `tools/cellsdb.py` | parses the PDK's functional Verilog into primitive gate lists |
| `tools/sim.py` | levelized zero-delay gate and flop simulator |
| `tools/verify_warmup.py` | extracts the warm-up GDS and checks it against A + B == 496 |
| `tools/satsolve.py` | CNF unrolling and solve |
| `tools/satall.py` | the same, but enumerates every solution to prove uniqueness |
| `tools/regions.py` | probes the netlist to recover the region map |
| `tools/expr.py`, `tools/an05.py` | net to boolean expression dumper, for reading the logic by hand |
| `tools/modes.py`, `tools/modes2.py` | enumerates the output generator's four messages |
| `tools/final_verify.py` | end-to-end replay straight from `puzzle.gds` |
| `tools/emit_results.py` | writes `results/` out as plain text |
| `tools/blocks.py` | assigns every cell to a functional block, for the floorplan figure |
| `tools/wavedata.py` | captures the signal trace around the input/output boundary |
| `tools/figures.py` | draws the figures in `figures/` as SVG |

## What is not in this repo

The puzzle files and the PDK are not redistributed here, since both have upstream
homes. Clone them next to the tools and everything below works.

## Reproducing it

```bash
pip install gdstk python-sat

git clone --depth 1 https://github.com/janestreet/asic-puzzle-2026
git clone --depth 1 https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd sky130hd

python tools/cellsdb.py tools/used.json                                 # parse the PDK cell models
python tools/verify_warmup.py                                           # prove the extractor on known ground truth
python tools/extract2.py asic-puzzle-2026/puzzle.gds puzzle puzzle.pkl  # GDS -> netlist
python tools/satall.py                                                  # solve, and prove the solution is unique
python tools/regions.py                                                 # recover the region map
python tools/final_verify.py                                            # replay from raw GDS, read the answer
python tools/emit_results.py results                                    # rewrite results/ as plain text
```

Run everything from the repository root. Expected output from the last real step:

```
during reset: success = 0
first cycle after input: success = 1
success held high: True
ANSWER STRING: '(* TWO STARS *)'
```

## Results

Everything in `results/` is plain text, generated by the pipeline above.

| File | Contents |
| --- | --- |
| `results/answer.txt` | the recovered string |
| `results/input_bits.txt` | the unique 121-bit input |
| `results/puzzle.txt` | the recovered Star Battle grid, unsolved |
| `results/solution.txt` | the same grid with the solution marked |
| `results/region_map.txt` | region membership per cell, plus region sizes |
| `results/results.json` | all of the above, machine readable |

`figures/` holds the diagrams used in the blog post: the recovered grid solved and
unsolved, the die with each recovered functional block highlighted, and a waveform
of the replay.

## Closing thought

The thing I'd tell anyone attempting something like this is: spend your first hour on the
warm-up, not the puzzle. Extraction is the kind of task where being 99% right feels
identical to being 100% right until suddenly it doesn't, and the warm-up is the only
place you can tell the difference. Every hour I spent making `A + B == 496` come back
out of a GDS file paid for itself, because after that I never had to wonder whether a
strange-looking piece of logic was a real design decision or a bug in my own
extractor. When `EMPTY SKY` scrolled past on a bus I'd reconstructed from rectangles
and vias, I knew it was the chip talking and not me.
