"""Emit the puzzle results as plain text, so nothing in the repo is an opaque pickle."""
import pickle, json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "results"
os.makedirs(OUT, exist_ok=True)

bits = pickle.load(open("solbits.pkl", "rb"))
region = pickle.load(open("regionmap.pkl", "rb"))["region"]
N = 11
LET = "ABCDEFGHIJK"
g = [bits[r * N:(r + 1) * N] for r in range(N)]

with open(os.path.join(OUT, "answer.txt"), "w", newline="\n") as fh:
    fh.write("(* TWO STARS *)\n")

with open(os.path.join(OUT, "input_bits.txt"), "w", newline="\n") as fh:
    fh.write("".join(map(str, bits)) + "\n")

def top_edge(r, c):  return r == 0 or region[r - 1][c] != region[r][c]
def left_edge(r, c): return c == 0 or region[r][c - 1] != region[r][c]

def render(show_stars):
    lines = []
    for r in range(N):
        lines.append("".join("+" + ("---" if top_edge(r, c) else "   ") for c in range(N)) + "+")
        row = ""
        for c in range(N):
            row += "|" if left_edge(r, c) else " "
            row += " %s " % ("*" if (show_stars and g[r][c]) else " ")
        lines.append(row + "|")
    lines.append("+" + "---+" * N)
    return "\n".join(lines)

with open(os.path.join(OUT, "puzzle.txt"), "w", newline="\n") as fh:
    fh.write("Star Battle, 11x11, 2 stars per row / column / region.\n")
    fh.write("Recovered from puzzle.gds by probing the extracted netlist.\n\n")
    fh.write(render(False) + "\n")

with open(os.path.join(OUT, "solution.txt"), "w", newline="\n") as fh:
    fh.write("The unique solution (verified by SAT enumeration).\n\n")
    fh.write(render(True) + "\n\n")
    fh.write("As a bit grid, row-major, which is the order the chip reads them:\n\n")
    for r in range(N):
        fh.write("  " + "".join(str(v) for v in g[r]) + "\n")

with open(os.path.join(OUT, "region_map.txt"), "w", newline="\n") as fh:
    fh.write("Region membership per cell, recovered by single-star probing.\n\n")
    for r in range(N):
        fh.write("  " + " ".join(LET[region[r][c]] for c in range(N)) + "\n")
    fh.write("\nRegion sizes:\n")
    for k in range(N):
        n = sum(1 for r in range(N) for c in range(N) if region[r][c] == k)
        fh.write(f"  {LET[k]}: {n} cells\n")

json.dump(
    {
        "answer": "(* TWO STARS *)",
        "input_bits": "".join(map(str, bits)),
        "grid": ["".join(map(str, row)) for row in g],
        "region_map": ["".join(LET[region[r][c]] for c in range(N)) for r in range(N)],
    },
    open(os.path.join(OUT, "results.json"), "w", newline="\n"),
    indent=2,
)

print("wrote:", sorted(os.listdir(OUT)))
