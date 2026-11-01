"""World map (Equal Earth) of inverted time-zone city pairs, with a grid of
same-scale zoomed panels below it.

Input: output/inverted_pairs_100k_200km_ew50_per_border.csv (from map_world.py --one-per-border).
Each panel uses a local azimuthal equidistant projection at the same scale, so
distances are comparable across panels. One panel per pair.
"""
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).parent))  # shared helpers, also under `python -I`
from mapkit import COLORS, INK, INK2, LABELS, SURFACE, dot_size, draw_panel, draw_world, draw_zone_key, load, world_frame

PANEL_W_KM, PANEL_H_KM = 440, 340  # every panel shows the same ground extent
NCOLS = 9

d = load()
pairs = d.pairs
_, (gx0, y_south, gx1, gy1) = world_frame()
world_aspect = (gy1 - y_south) / (gx1 - gx0)

# --- figure ---
nrows = math.ceil(len(pairs) / NCOLS)
FIG_W, MARGIN, GAP_X, GAP_Y = 16.0, 0.3, 0.13, 0.5  # inches
HEAD, LEGEND_H, FOOT = 1.05, 0.62, 0.62
WORLD_H = (FIG_W - 2 * MARGIN) * world_aspect
PANEL_W = (FIG_W - 2 * MARGIN - (NCOLS - 1) * GAP_X) / NCOLS
PANEL_H = PANEL_W * PANEL_H_KM / PANEL_W_KM
FIG_H = HEAD + WORLD_H + LEGEND_H + nrows * PANEL_H + (nrows - 1) * GAP_Y + 0.42 + FOOT
fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor=SURFACE)
def axes_in(x, y_top, w, h):  # inches from top-left -> figure fraction
    return fig.add_axes([x / FIG_W, 1 - (y_top + h) / FIG_H, w / FIG_W, h / FIG_H])

# world map
ax = axes_in(MARGIN, HEAD, FIG_W - 2 * MARGIN, WORLD_H)
draw_world(ax, d)
draw_zone_key(ax, [0.035, 0.07, 0.24, 0.022])
season_handles = [Line2D([], [], color=c, lw=2, marker="o", markersize=6, markeredgecolor=SURFACE)
                  for c in COLORS.values()]
season_labels = [f"{LABELS[k]} ({n} pair{'' if n == 1 else 's'})" for k in COLORS for n in [(pairs.inverted_in == k).sum()]]
ax.add_artist(ax.legend(season_handles, season_labels, title="Panel colors: when the eastern city is behind",
                        loc="upper left", bbox_to_anchor=(0, -0.005), ncol=3, frameon=False, fontsize=9.5,
                        title_fontsize=9, labelcolor=INK2, alignment="left", handlelength=2.2))
# dot-size key for the panels
size_keys = [250_000, 1_000_000, 3_000_000]
handles = [ax.scatter([], [], s=dot_size(np.array(p)), color=INK2, edgecolor=SURFACE) for p in size_keys]
ax.legend(handles, [f"{p / 1e6:g}M" for p in size_keys], title="Panel dots: metro population", loc="upper right",
          bbox_to_anchor=(1, -0.0), ncol=3, frameon=False, fontsize=9, title_fontsize=9, labelcolor=INK2,
          handletextpad=0.3, columnspacing=1.2, borderaxespad=0.2, alignment="left")
fig.text(MARGIN / FIG_W, 1 - 0.3 / FIG_H, "Nearby cities where the eastern one is on an earlier clock", fontsize=17, fontweight="bold",
         color=INK, va="top")
fig.text(MARGIN / FIG_W, 1 - 0.62 / FIG_H, f"{len(pairs)} city pairs (largest per border): ≤200 km apart, eastern city ≥50 km further east, "
         "both ≥100k people. Time zones shaded by UTC offset, darker toward ±12 h. Numbers refer to the panels below.",
         fontsize=10.5, color=INK2, va="top")

# panels
for i in pairs.index:
    row, col = divmod(i, NCOLS)
    pax = axes_in(MARGIN + col * (PANEL_W + GAP_X), HEAD + WORLD_H + LEGEND_H + 0.42 + row * (PANEL_H + GAP_Y),
                  PANEL_W, PANEL_H)
    draw_panel(pax, d, i, PANEL_W_KM, PANEL_H_KM, PANEL_W, scale_bar=(i == 0))

fig.text(MARGIN / FIG_W, 0.12 / FIG_H, f"All panels same scale ({PANEL_W_KM} × {PANEL_H_KM} km), local azimuthal equidistant projection; "
         "dark lines are time zone boundaries and coastlines, white lines country borders; km = distance between the two cities.\n"
         "City offsets shown as UTC winter (from 1 Nov 2026) / summer 2027. Panel dot size scales with metro population (Natural Earth POP_MAX).\n"
         "Data: Natural Earth v5.1.2; timezone-boundary-builder 2026e / IANA tzdata 2026e (© OpenStreetMap contributors, ODbL). "
         "World map: Equal Earth.", fontsize=7.5, color=INK2)
fig.savefig("output/map_inverted_pairs_with_panels.png", dpi=200, facecolor=SURFACE)
fig.savefig("output/map_inverted_pairs_with_panels.svg", dpi=200, facecolor=SURFACE)
