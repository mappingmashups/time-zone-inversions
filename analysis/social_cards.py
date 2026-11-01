"""Square images for social media (1800 x 1800 px PNG, plus JPEG copies).

1. Seattle-Vancouver headline map   2. world overview with the list of pairs
3. panels 1-9                       4. panels 10-18
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))  # shared helpers, also under `python -I`
from mapkit import COLORS, INK, INK2, LABELS, SURFACE, draw_panel, draw_world, draw_zone_key, load, world_frame

SIZE, DPI = 6.0, 300  # inches, dots per inch -> 1800 px
M = 0.32  # outer margin (in)
OUT = Path("output/social")
URL = "mappingmashups.github.io/time-zone-inversions"
CREDIT = "Data: Natural Earth · timezone-boundary-builder, © OpenStreetMap contributors (ODbL) · IANA tz 2026e"

d = load()
pairs = d.pairs
OUT.mkdir(parents=True, exist_ok=True)


def new_card():
    fig = plt.figure(figsize=(SIZE, SIZE), facecolor=SURFACE)
    def axes_in(x, y_top, w, h):  # inches from top-left -> figure fraction
        return fig.add_axes([x / SIZE, 1 - (y_top + h) / SIZE, w / SIZE, h / SIZE])
    return fig, axes_in


def text(fig, x, y_top, s, **kw):
    return fig.text(x / SIZE, 1 - y_top / SIZE, s, va="top", **kw)


def footer(fig, extra=""):
    text(fig, M, SIZE - 0.42, f"{URL}{extra}", fontsize=7.5, color=INK, fontweight="bold")
    text(fig, M, SIZE - 0.26, CREDIT, fontsize=5.6, color=INK2)


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=DPI, facecolor=SURFACE)
    fig.savefig(OUT / f"{name}.jpg", dpi=DPI, facecolor=SURFACE, pil_kwargs={"quality": 90})
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


# --- 1. Seattle / Vancouver ---
fig, axes_in = new_card()
text(fig, M, 0.32, "From today, Seattle is an hour\nbehind Vancouver", fontsize=19, fontweight="bold", color=INK,
     linespacing=1.1)
text(fig, M, 1.13, "…even though Seattle is 60 km further east. British Columbia now stays on UTC−7\n"
     "all year, while Washington falls back to UTC−8 for the winter.", fontsize=8.6, color=INK2, linespacing=1.35)
mw = SIZE - 2 * M
mh = 3.85
sv = pairs.index[pairs.west.str.startswith("Vancouver")][0]
pax = axes_in(M, 1.62, mw, mh)
SV_W = 420  # km across
draw_panel(pax, d, sv, SV_W, SV_W * mh / mw, mw, label_size=10.5, dot_scale=1.9, line_width=3, line_scale=1.4,
           title=False, scale_bar=False)
x0, y0 = -SV_W * 500 + SV_W * 34, -SV_W * mh / mw * 500 + 12000
pax.plot([x0, x0 + 50000], [y0, y0], color=INK, lw=2, solid_capstyle="butt", zorder=6)
pax.text(x0 + 25000, y0 + 4000, "50 km", ha="center", va="bottom", fontsize=8, color=INK, zorder=6)
footer(fig, "  ·  #30DayMapChallenge Day 1: Points")
save(fig, "1_seattle_vancouver")

# --- 2. world overview ---
fig, axes_in = new_card()
text(fig, M, 0.32, "Seattle and Vancouver aren't alone", fontsize=17, fontweight="bold", color=INK)
text(fig, M, 0.74, f"{len(pairs)} pairs of nearby cities where the eastern one is on an earlier clock", fontsize=9,
     color=INK2)
_, (gx0, y0, gx1, gy1) = world_frame()
ww = SIZE - 2 * M
wh = ww * (gy1 - y0) / (gx1 - gx0)
ax = axes_in(M, 1.08, ww, wh)
draw_world(ax, d, scale=0.75, number_size=7)
draw_zone_key(ax, [0.035, 0.08, 0.27, 0.035], fontsize=5.5, title="UTC offset from 1 Nov 2026")
# list of pairs in three columns
top = 1.08 + wh + 0.2
rows_per_col = 6
for i, r in pairs.iterrows():
    col, row = divmod(i, rows_per_col)
    x, y = M + (0, 1.95, 3.7)[col], top + row * 0.29  # columns sized to the longest pair names
    text(fig, x, y, f"{r.n}", fontsize=7.2, color=INK, fontweight="bold")
    text(fig, x + 0.2, y, f"{r.west.split(',')[0]} → {r.east.split(',')[0]}", fontsize=7.2, color=INK)
text(fig, M, top + rows_per_col * 0.29 + 0.06, "Cities ≥100k people, ≤200 km apart, eastern city ≥50 km further east.",
     fontsize=6.6, color=INK2)
footer(fig)
save(fig, "2_world")

# --- 3 and 4. panel grids ---
PW_KM, PH_KM = 440, 320  # same scale as the main map's panels, a little shorter to fit 3 rows
gap_x, gap_y, head = 0.16, 0.3, 1.15
pw = (SIZE - 2 * M - 2 * gap_x) / 3
ph = pw * PH_KM / PW_KM
for card, (first, last) in enumerate([(0, 9), (9, 18)], start=3):
    fig, axes_in = new_card()
    text(fig, M, 0.32, f"Wrong-way clocks: pairs {first + 1}–{last}", fontsize=15, fontweight="bold", color=INK)
    handles = [plt.Line2D([], [], color=c, lw=2, marker="o", markersize=5, markeredgecolor=SURFACE)
               for c in COLORS.values()]
    fig.legend(handles, [f"East city behind: {LABELS[k].lower()}" if k == "jan,jul" else LABELS[k] for k in COLORS],
               loc="upper left", bbox_to_anchor=(M / SIZE - 0.008, 1 - 0.62 / SIZE), ncol=3, frameon=False,
               fontsize=7.2, labelcolor=INK2, handlelength=1.8, columnspacing=1.2)
    for j, i in enumerate(range(first, last)):
        row, col = divmod(j, 3)
        pax = axes_in(M + col * (pw + gap_x), head + row * (ph + gap_y), pw, ph)
        draw_panel(pax, d, i, PW_KM, PH_KM, pw, label_size=6.2, dot_scale=1.05, title_size=6.9,
                   title_one_line=True, scale_bar=(j == 0))
    footer(fig, "  ·  same scale in every panel")
    save(fig, f"{card}_pairs_{first + 1}-{last}")
