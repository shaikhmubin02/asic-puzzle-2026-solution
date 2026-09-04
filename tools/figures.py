"""Generate the three blog figures as SVG.

Palette: the site's own tokens (light mode only), with one accent hue for the
data. Accent validated against a white surface: lightness band, chroma floor and
3:1 contrast all pass.
"""
import json, pickle, math, sys, os

INK    = "#090909"   # --foreground
MUTED  = "#636363"   # --muted-foreground
BORDER = "#e1e1e1"   # --border
FAINT  = "#d4d4d4"   # de-emphasis for the die texture
ACCENT = "#2a78d6"   # categorical slot 1
FONT   = 'system-ui,-apple-system,"Segoe UI",sans-serif'

OUT = sys.argv[1] if len(sys.argv) > 1 else "figures"
os.makedirs(OUT, exist_ok=True)


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img" aria-label="{title}" '
            f'font-family=\'{FONT}\'>\n<title>{title}</title>\n{body}\n</svg>\n')


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------- figure 1
def star(cx, cy, r):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.42
        pts.append(f"{cx + rr * math.cos(a):.2f},{cy + rr * math.sin(a):.2f}")
    return " ".join(pts)


def fig_puzzle(region, grid, path, with_stars):
    N, C, M = 11, 38, 18
    W = H = N * C + 2 * M
    p = []
    p.append(f'<rect x="{M}" y="{M}" width="{N*C}" height="{N*C}" fill="#ffffff"/>')
    # cell hairlines
    for i in range(1, N):
        p.append(f'<line x1="{M+i*C}" y1="{M}" x2="{M+i*C}" y2="{M+N*C}" stroke="{BORDER}" stroke-width="1"/>')
        p.append(f'<line x1="{M}" y1="{M+i*C}" x2="{M+N*C}" y2="{M+i*C}" stroke="{BORDER}" stroke-width="1"/>')
    # stars
    if with_stars:
        for r in range(N):
            for c in range(N):
                if grid[r][c]:
                    p.append(f'<polygon points="{star(M+c*C+C/2, M+r*C+C/2, 11.5)}" fill="{ACCENT}"/>')
    # region borders, drawn last so they sit on top
    seg = []
    for r in range(N):
        for c in range(N):
            if r == 0 or region[r-1][c] != region[r][c]:
                seg.append((M+c*C, M+r*C, M+(c+1)*C, M+r*C))
            if c == 0 or region[r][c-1] != region[r][c]:
                seg.append((M+c*C, M+r*C, M+c*C, M+(r+1)*C))
    seg.append((M, M+N*C, M+N*C, M+N*C))
    seg.append((M+N*C, M, M+N*C, M+N*C))
    for x1, y1, x2, y2 in seg:
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{INK}" '
                 f'stroke-width="2.6" stroke-linecap="square"/>')
    t = "Recovered Star Battle puzzle with its unique solution" if with_stars else "Recovered Star Battle puzzle"
    open(path, "w", encoding="utf-8").write(svg(W, H, "\n".join(p), t))
    return W, H


# ---------------------------------------------------------------- figure 2
def fig_floorplan(fp, path):
    DIE_W, DIE_H = 200.0, 300.0
    SC = 0.64
    PW, PH = DIE_W * SC, DIE_H * SC
    COLS, LAB, GAPX, GAPY, M = 4, 17, 16, 30, 14
    blocks = fp["blocks"]
    rows = (len(blocks) + COLS - 1) // COLS
    W = int(M * 2 + COLS * PW + (COLS - 1) * GAPX)
    H = int(M * 2 + rows * (LAB + PH) + (rows - 1) * GAPY) + 12
    by_block = {}
    for c in fp["cells"]:
        by_block.setdefault(c["b"], []).append(c)
    die = []
    for c in fp["cells"]:
        die.append(f'<rect x="{c["x"]*SC:.2f}" y="{(DIE_H-c["y"]-c["h"])*SC:.2f}" '
                   f'width="{max(c["w"]*SC,0.7):.2f}" height="{max(c["h"]*SC,1.0):.2f}"/>')
    p = [f'<defs><g id="die" fill="{FAINT}">' + "".join(die) + '</g></defs>']
    for idx, b in enumerate(blocks):
        col, row = idx % COLS, idx // COLS
        ox = M + col * (PW + GAPX)
        oy = M + row * (LAB + PH + GAPY) + LAB
        n = len(by_block.get(b["key"], []))
        p.append(f'<text x="{ox:.1f}" y="{oy-6:.1f}" font-size="10.5" font-weight="550" '
                 f'fill="{INK}">{esc(b["label"])}</text>')
        p.append(f'<rect x="{ox:.1f}" y="{oy:.1f}" width="{PW:.1f}" height="{PH:.1f}" '
                 f'fill="none" stroke="{BORDER}" stroke-width="1"/>')
        # whole die, recessive
        p.append(f'<use href="#die" x="{ox:.1f}" y="{oy:.1f}"/>')
        # this block, emphasised
        for c in by_block.get(b["key"], []):
            x = ox + c["x"] * SC
            y = oy + (DIE_H - c["y"] - c["h"]) * SC
            p.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(c["w"]*SC,1.3):.2f}" '
                     f'height="{max(c["h"]*SC,1.4):.2f}" fill="{ACCENT}"/>')
        p.append(f'<text x="{ox+PW/2:.1f}" y="{oy+PH+13:.1f}" font-size="9.5" '
                 f'text-anchor="middle" fill="{MUTED}">{b["nff"]} flops, {n} cells</text>')
    # key, in the empty slot
    if len(blocks) % COLS:
        col, row = len(blocks) % COLS, len(blocks) // COLS
        ox = M + col * (PW + GAPX)
        oy = M + row * (LAB + PH + GAPY) + LAB
        p.append(f'<text x="{ox:.1f}" y="{oy+14:.1f}" font-size="10.5" font-weight="550" fill="{INK}">Key</text>')
        for k, (sw, lb) in enumerate([(ACCENT, "cells in this block"), (FAINT, "rest of the die")]):
            yy = oy + 34 + k * 19
            p.append(f'<rect x="{ox:.1f}" y="{yy-8:.1f}" width="11" height="11" fill="{sw}"/>')
            p.append(f'<text x="{ox+17:.1f}" y="{yy+1:.1f}" font-size="10" fill="{MUTED}">{lb}</text>')
        p.append(f'<text x="{ox:.1f}" y="{oy+90:.1f}" font-size="10" fill="{MUTED}">942 cells total,</text>')
        p.append(f'<text x="{ox:.1f}" y="{oy+104:.1f}" font-size="10" fill="{MUTED}">200 x 300 um die.</text>')
        p.append(f'<text x="{ox:.1f}" y="{oy+126:.1f}" font-size="10" fill="{MUTED}">Blocks recovered</text>')
        p.append(f'<text x="{ox:.1f}" y="{oy+140:.1f}" font-size="10" fill="{MUTED}">from the netlist,</text>')
        p.append(f'<text x="{ox:.1f}" y="{oy+154:.1f}" font-size="10" fill="{MUTED}">not the layout.</text>')
    open(path, "w", encoding="utf-8").write(
        svg(W, H, "\n".join(p), "Die floorplan, one panel per recovered functional block"))
    return W, H


# ---------------------------------------------------------------- figure 3
def fig_wave(wd, path):
    rows_d = wd["rows"]
    tail = wd["tail"]
    n = len(rows_d)
    CW, LEFT, M, RH, RG, TOP = 31, 82, 14, 26, 22, 46
    W = LEFT + n * CW + M + 8
    sigs = ["clk", "enable", "success", "O[7:0]"]
    BOT = TOP + len(sigs) * (RH + RG) - RG
    H = BOT + 14
    p = []

    def lvl(y0, vals, stroke, wdt="2"):
        d = []
        for i, v in enumerate(vals):
            x = LEFT + i * CW
            yv = y0 + (0 if v else RH)
            if i == 0:
                d.append(f"M{x},{yv}")
            else:
                py = y0 + (0 if vals[i-1] else RH)
                if py != yv:
                    d.append(f"L{x},{py}L{x},{yv}")
                else:
                    d.append(f"L{x},{yv}")
            d.append(f"L{x+CW},{yv}")
        return (f'<path d="{"".join(d)}" fill="none" stroke="{stroke}" '
                f'stroke-width="{wdt}" stroke-linejoin="miter"/>')

    # cycle ruler
    for i, r in enumerate(rows_d):
        x = LEFT + i * CW
        p.append(f'<line x1="{x}" y1="{TOP-8}" x2="{x}" y2="{BOT}" stroke="{BORDER}" stroke-width="1"/>')
        p.append(f'<text x="{x+CW/2}" y="{TOP-12}" font-size="8.5" text-anchor="middle" '
                 f'fill="{MUTED}">{r["lbl"]}</text>')
    p.append(f'<line x1="{LEFT+n*CW}" y1="{TOP-8}" x2="{LEFT+n*CW}" y2="{BOT}" stroke="{BORDER}" stroke-width="1"/>')

    # phase boundary
    bx = LEFT + tail * CW
    p.append(f'<line x1="{bx}" y1="{TOP-34}" x2="{bx}" y2="{BOT}" stroke="{MUTED}" stroke-width="1.5"/>')
    p.append(f'<text x="{bx-8}" y="{16}" font-size="10" text-anchor="end" fill="{MUTED}">input phase</text>')
    p.append(f'<text x="{bx+8}" y="{16}" font-size="10" fill="{MUTED}">output phase</text>')

    for si, s in enumerate(sigs):
        y0 = TOP + si * (RH + RG)
        p.append(f'<text x="{LEFT-10}" y="{y0+RH/2+3.5}" font-size="11" text-anchor="end" '
                 f'fill="{INK}">{esc(s)}</text>')
        if s == "clk":
            v = []
            for _ in range(n):
                v += [0, 1]
            d = []
            for i in range(n):
                x = LEFT + i * CW
                d.append(f'M{x},{y0+RH}L{x},{y0}L{x+CW/2},{y0}L{x+CW/2},{y0+RH}L{x+CW},{y0+RH}')
            p.append(f'<path d="{"".join(d)}" fill="none" stroke="{MUTED}" stroke-width="1.6"/>')
        elif s == "enable":
            p.append(lvl(y0, [r["en"] for r in rows_d], MUTED, "1.8"))
        elif s == "success":
            p.append(lvl(y0, [r["succ"] for r in rows_d], ACCENT, "2.4"))
        else:
            for i, r in enumerate(rows_d):
                x, o = LEFT + i * CW, r["o"]
                if o == 0:
                    p.append(f'<line x1="{x}" y1="{y0+RH}" x2="{x+CW}" y2="{y0+RH}" '
                             f'stroke="{MUTED}" stroke-width="1.8"/>')
                else:
                    b = 3.5
                    p.append(f'<path d="M{x+b},{y0} L{x+CW-b},{y0} L{x+CW},{y0+RH/2} '
                             f'L{x+CW-b},{y0+RH} L{x+b},{y0+RH} L{x},{y0+RH/2} Z" '
                             f'fill="none" stroke="{ACCENT}" stroke-width="1.8"/>')
                    lab = r["ch"] if r["ch"].strip() else "SP"
                    p.append(f'<text x="{x+CW/2}" y="{y0+RH/2+4}" font-size="11.5" '
                             f'font-weight="550" text-anchor="middle" fill="{INK}">{esc(lab)}</text>')
    open(path, "w", encoding="utf-8").write(
        svg(W, H, "\n".join(p), "Waveform: success rises one cycle after the last input bit, then O clocks out the answer"))
    return W, H


if __name__ == "__main__":
    region = pickle.load(open("regionmap.pkl", "rb"))["region"]
    bits = pickle.load(open("solbits.pkl", "rb"))
    grid = [bits[r*11:(r+1)*11] for r in range(11)]
    fp = json.load(open("floorplan.json"))
    wd = json.load(open("wavedata.json"))
    print("star-battle-puzzle.svg  ", fig_puzzle(region, grid, f"{OUT}/star-battle-puzzle.svg", False))
    print("star-battle-solution.svg", fig_puzzle(region, grid, f"{OUT}/star-battle-solution.svg", True))
    print("asic-floorplan.svg      ", fig_floorplan(fp, f"{OUT}/asic-floorplan.svg"))
    print("asic-waveform.svg       ", fig_wave(wd, f"{OUT}/asic-waveform.svg"))
