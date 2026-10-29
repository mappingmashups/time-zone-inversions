"""World map (Equal Earth) of inverted time-zone city pairs, with a grid of
same-scale zoomed panels below it.

Input: output/inverted_pairs_100k_200km_ew50_per_border.csv (from map_world.py --one-per-border).
Each panel uses a local azimuthal equidistant projection at the same scale, so
distances are comparable across panels. One panel per pair.
"""
import math
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from adjustText import adjust_text
from pyproj import Geod, Transformer
from shapely.geometry import LineString, box

WORLD_CRS = "EPSG:8857"  # Equal Earth
PANEL_W_KM, PANEL_H_KM = 440, 340  # every panel shows the same ground extent
NCOLS = 9
# --panel-dots-ink: panel dots in ink too, season colour only on the connecting line
PANEL_DOTS_INK = "--panel-dots-ink" in sys.argv
SUFFIX = "_inkdots" if PANEL_DOTS_INK else ""
# simplification tolerances (metres), ~0.1 pt at print size: keeps the SVG light without visible change
WORLD_TOL, PANEL_TOL = 3000, 300
PAIR_INK = "#34322e"  # world-map dots and links: one neutral colour

COLORS = {"jan,jul": "#2a78d6", "jan": "#eb6834", "jul": "#1baf7a"}  # dataviz reference slots 1-3
LABELS = {"jan,jul": "All year", "jan": "Northern winter only",
          "jul": "Northern summer only"}
SURFACE, OCEAN, LAND, TZ, TZ_STRONG, INK, INK2 = "#fcfcfb", "#f1f4f6", "#e4e3df", "#b9b8b2", "#52514e", "#0b0b0b", "#52514e"
SHORT = {"Pedro Juan Caballero": "Pedro Juan\nCaballero"}  # wrap long labels in the small panels
# Panel dot area (pt²) grows linearly with metro population (Natural Earth POP_MAX) between a floor and a
# ceiling: the largest city keeps its area-true size, the smallest gets 2x the diameter it had under strict scaling.
DOT_POP_MIN, DOT_AREA_MIN = 100_000, 48
DOT_POP_MAX, DOT_AREA_MAX = 5_183_700, 5_183_700 * 65 / 1e6  # Singapore, the largest city in the panels
def dot_size(pop):
    t = (np.asarray(pop, dtype=float) - DOT_POP_MIN) / (DOT_POP_MAX - DOT_POP_MIN)
    return DOT_AREA_MIN + np.clip(t, 0, 1) * (DOT_AREA_MAX - DOT_AREA_MIN)


# "jan" = northern winter: offsets at noon on 1 Nov 2026 are identical to mid-Jan 2027 for every zone (tzdata 2026e)
DATES = {"jan": datetime(2026, 11, 1, 12), "jul": datetime(2027, 7, 15, 12)}

geod = Geod(ellps="WGS84")
pairs = pd.read_csv("output/inverted_pairs_100k_200km_ew50_per_border.csv")
pairs = pairs.assign(mid_lon=(pairs.west_lon + pairs.east_lon) / 2).sort_values("mid_lon").reset_index(drop=True)


def offset_label(tzid):
    """'UTC−8 / −7' (Jan / Jul) or 'UTC+5:30' when the same all year."""
    def fmt(h):
        sign = "+" if h >= 0 else "−"
        hh, mm = divmod(round(abs(h) * 60), 60)
        return f"{sign}{hh}" + (f":{mm:02d}" if mm else "")
    jan, jul = (DATES[k].replace(tzinfo=ZoneInfo(tzid)).utcoffset().total_seconds() / 3600 for k in DATES)
    return f"UTC{fmt(jan)}" if jan == jul else f"UTC{fmt(jan)} / {fmt(jul)}"


def oklch_to_hex(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_, m_, s_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, \
                 (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    enc = lambda c: 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return "#" + "".join(f"{round(min(max(enc(min(max(c, 0), 1)), 0), 1) * 255):02x}" for c in rgb)


def zone_fill(offset_h):
    """Pastel rainbow by UTC offset, west (violet) -> noon (yellow) -> east (rose); dims toward ±12 h like night."""
    hue = np.interp(offset_h, [-12, -8, -4, 0, 4, 8, 12], [295, 250, 185, 105, 70, 40, 5])
    night = (1 - math.cos(math.pi * min(abs(offset_h), 12) / 12)) / 2  # 0 at UTC, 1 at ±12
    soften_yellow = 1 - 0.45 * math.exp(-(((hue - 95) / 22) ** 2))  # yellows read brighter than other hues
    return oklch_to_hex(0.95 - 0.21 * night, (0.055 + 0.01 * night) * soften_yellow, hue)


def aeqd(lon, lat):
    return f"+proj=aeqd +lat_0={lat:.4f} +lon_0={lon:.4f} +datum=WGS84 +units=m"


# one panel per pair, numbered west to east
clusters = [{"rows": [i], "lons": [r.west_lon, r.east_lon], "lats": [r.west_lat, r.east_lat], "n": i + 1}
            for i, r in pairs.iterrows()]


# --- shared layers ---
land50 = gpd.read_file("data/raw/natural_earth/ne_50m_admin_0_countries_lakes.shp")
land10 = gpd.read_file("data/raw/natural_earth/ne_10m_admin_0_countries_lakes.shp")
tz_now = gpd.read_file("data/raw/timezones/timezones-with-oceans-now.shapefile/combined-shapefile-with-oceans-now.shp")
tz_edges = tz_now.boundary.clip_by_rect(-179.99, -89.99, 179.99, 89.99)
tz_now["offset"] = [DATES["jan"].replace(tzinfo=ZoneInfo(t)).utcoffset().total_seconds() / 3600 for t in tz_now.tzid]
tz_now["fill"] = tz_now.offset.map(zone_fill)
OCEAN_FADE = dict(color=OCEAN, alpha=0.85, edgecolor="none")  # mutes time zone colors at sea


def geodesic(r, n=16):
    mid = geod.npts(r.west_lon, r.west_lat, r.east_lon, r.east_lat, n)
    return LineString([(r.west_lon, r.west_lat), *mid, (r.east_lon, r.east_lat)])


lines = gpd.GeoDataFrame(pairs, geometry=[geodesic(r) for r in pairs.itertuples()], crs=4326)
pts = pd.concat([pairs[[f"{s}", f"{s}_lon", f"{s}_lat", f"{s}_tz", f"{s}_pop", "inverted_in"]].set_axis(["name", "lon", "lat", "tz", "pop", "k"], axis=1)
                 .assign(side=s) for s in ("west", "east")]).drop_duplicates("name")
pts = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326)

# --- world map frame: Equal Earth outline, cropped just south of Cape Horn (no Antarctica) ---
SOUTH_LAT = -57
edge = [(-180, y) for y in range(-90, 91)] + [(180, y) for y in range(90, -91, -1)]
globe_poly = gpd.GeoSeries([LineString(edge)], crs=4326).to_crs(WORLD_CRS).iloc[0].convex_hull
y_south = Transformer.from_crs(4326, WORLD_CRS, always_xy=True).transform(0, SOUTH_LAT)[1]
gx0, _, gx1, gy1 = globe_poly.bounds
map_shape = globe_poly.intersection(box(gx0, y_south, gx1, gy1))
world_aspect = (gy1 - y_south) / (gx1 - gx0)

# --- figure ---
nrows = math.ceil(len(clusters) / NCOLS)
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
ax.set_facecolor(SURFACE)
wz = tz_now.set_geometry(tz_now.geometry.segmentize(0.5)).to_crs(WORLD_CRS)
wz = wz.set_geometry(wz.geometry.simplify(WORLD_TOL).make_valid()).clip(map_shape)
wz.plot(ax=ax, color=wz.fill, edgecolor="none", zorder=0)
wland = land50[land50.ADM0_A3 != "ATA"].to_crs(WORLD_CRS)
wland = wland.set_geometry(wland.geometry.simplify(WORLD_TOL).make_valid()).clip(map_shape)
wland_union = wland.geometry.make_valid().union_all()
wedges = tz_edges.segmentize(0.5).to_crs(WORLD_CRS).simplify(WORLD_TOL).clip(map_shape)
wedges.plot(ax=ax, color=TZ_STRONG, alpha=0.35, linewidth=0.3, zorder=0.5)  # at sea: faded by the mask
gpd.GeoSeries([map_shape.difference(wland_union)], crs=WORLD_CRS).plot(ax=ax, **OCEAN_FADE, zorder=1)
wland.boundary.plot(ax=ax, color="white", linewidth=0.35, zorder=1.5)
wedges.intersection(wland_union).plot(ax=ax, color=TZ_STRONG, alpha=0.6, linewidth=0.4, zorder=1.7)  # on land: over borders
coast = wland_union.boundary.difference(map_shape.boundary.buffer(5000))  # drop artificial edges at the map frame
gpd.GeoSeries([coast], crs=WORLD_CRS).plot(ax=ax, color=TZ_STRONG, alpha=0.6, linewidth=0.4, zorder=1.7)
gpd.GeoSeries([map_shape.boundary], crs=WORLD_CRS).plot(ax=ax, color=TZ, linewidth=0.6, zorder=2)
wpts = pts.to_crs(WORLD_CRS)
wlines = lines.to_crs(WORLD_CRS)
# pass 1: one shared outline layer (lines + dots) so nearby pairs merge into a single haloed blob
W_DOT, W_LINE, W_HALO = 6.5, 2.4, 1.6  # dot diameter, line width, outline width (pt)
wlines.plot(ax=ax, color=SURFACE, linewidth=W_LINE + 2 * W_HALO, zorder=3.5, capstyle="round")
ax.scatter(wpts.geometry.x, wpts.geometry.y, s=(W_DOT + 2 * W_HALO) ** 2, color=SURFACE, linewidth=0, zorder=3.5)
# pass 2: lines and dots on top in a single ink, no individual edges (season colour lives in the panels)
wlines.plot(ax=ax, color=PAIR_INK, linewidth=W_LINE, zorder=3.8)
ax.scatter(wpts.geometry.x, wpts.geometry.y, s=W_DOT ** 2, color=PAIR_INK, linewidth=0, zorder=4)
# panel numbers on the world map
wt = Transformer.from_crs(4326, WORLD_CRS, always_xy=True)
texts = []
for c in clusters:
    x, y = wt.transform(np.mean(c["lons"]), np.mean(c["lats"]))
    texts.append(ax.text(x, y, str(c["n"]), fontsize=9, fontweight="bold", color=INK, zorder=5,
                         ha="center", va="center"))
adjust_text(texts, ax=ax, x=wpts.geometry.x.values, y=wpts.geometry.y.values, expand=(2.4, 2.4),
            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5), min_arrow_len=4)
ax.set_xlim(gx0, gx1); ax.set_ylim(y_south, gy1)
ax.set_rasterization_zorder(2.5)  # base map (z < 2.5) becomes an image in the SVG; symbols and text stay vector
ax.set_axis_off(); ax.set_aspect("equal")
key_offsets = list(range(-12, 15))
bg = ax.inset_axes([0.025, 0.035, 0.26, 0.085])
bg.set_facecolor(SURFACE); bg.patch.set_alpha(0.85); bg.set_xticks([]); bg.set_yticks([])
for sp in bg.spines.values():
    sp.set_visible(False)
kax = ax.inset_axes([0.035, 0.07, 0.24, 0.022])
kax.imshow([[matplotlib.colors.to_rgb(zone_fill(o)) for o in key_offsets]], aspect="auto",
           extent=(-12.5, 14.5, 0, 1))
kax.set_yticks([]); kax.set_xticks([-12, -6, 0, 6, 12])
kax.set_xticklabels(["−12", "−6", "0", "+6", "+12"], fontsize=7, color=INK2)
kax.tick_params(length=2, color=INK2, pad=1)
for sp in kax.spines.values():
    sp.set_visible(False)
kax.set_title("Time zone: UTC offset from 1 Nov 2026", fontsize=7.5, color=INK2, loc="left", pad=3)
season_handles = [Line2D([], [], color=c, lw=2, marker=None if PANEL_DOTS_INK else "o", markersize=6,
                         markeredgecolor=SURFACE) for c in COLORS.values()]
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
for idx, c in enumerate(clusters):
    row, col = divmod(idx, NCOLS)
    pax = axes_in(MARGIN + col * (PANEL_W + GAP_X), HEAD + WORLD_H + LEGEND_H + 0.42 + row * (PANEL_H + GAP_Y),
                  PANEL_W, PANEL_H)
    lon0, lat0 = np.mean(c["lons"]), np.mean(c["lats"])
    crs = aeqd(lon0, lat0)
    hw, hh = PANEL_W_KM * 500, PANEL_H_KM * 500
    # generous lon/lat window for clipping before projecting
    dlat = PANEL_H_KM / 111 * 0.9 + 1
    dlon = PANEL_W_KM / (111 * math.cos(math.radians(min(abs(lat0) + dlat, 85)))) * 0.9 + 1
    win = box(lon0 - dlon, lat0 - dlat, lon0 + dlon, lat0 + dlat)
    frame = box(-hw, -hh, hw, hh)
    pz = tz_now.clip(win)
    pz = pz.set_geometry(pz.geometry.segmentize(0.05)).to_crs(crs)
    pz = pz.set_geometry(pz.geometry.simplify(PANEL_TOL).make_valid()).clip(frame)
    pz.plot(ax=pax, color=pz.fill, edgecolor="none", zorder=0)
    pland = land10.clip(win).to_crs(crs)
    pland = pland.set_geometry(pland.geometry.simplify(PANEL_TOL).make_valid()).clip(frame)
    pedges = gpd.GeoSeries([tz_edges.clip(win).union_all()], crs=4326).segmentize(0.05).to_crs(crs).simplify(PANEL_TOL).clip(frame)
    pedges.plot(ax=pax, color=TZ_STRONG, linewidth=0.8, zorder=0.5)
    sea = frame.difference(pland.union_all())
    if not sea.is_empty:
        gpd.GeoSeries([sea], crs=crs).plot(ax=pax, **OCEAN_FADE, zorder=1)
    pland.boundary.plot(ax=pax, color="white", linewidth=0.8, zorder=1.5)
    pland_union = pland.geometry.make_valid().union_all()
    pcoast = pland_union.boundary.difference(frame.boundary.buffer(500))
    if not pcoast.is_empty:
        gpd.GeoSeries([pcoast], crs=crs).plot(ax=pax, color=TZ_STRONG, linewidth=0.6, zorder=1.7)
    on_land = pedges.intersection(pland_union)
    on_land = on_land[~on_land.is_empty]
    if len(on_land):
        on_land.plot(ax=pax, color=TZ_STRONG, linewidth=0.8, zorder=1.7)  # time zone line wins over border
    sub = pairs.loc[c["rows"]]
    lines.loc[c["rows"]].to_crs(crs).plot(ax=pax, color=[COLORS[k] for k in sub.inverted_in], linewidth=1.3, zorder=3)
    names = set(sub.west) | set(sub.east)
    pp = pts[pts.name.isin(names)].to_crs(crs)
    pp = pp.sort_values("pop", ascending=False)  # small dot on top if they overlap
    pax.scatter(pp.geometry.x, pp.geometry.y, s=dot_size(pp["pop"]), color=[PAIR_INK if PANEL_DOTS_INK else COLORS[k] for k in pp.k], edgecolor=SURFACE,
                linewidth=0.8, zorder=4)
    texts = []
    for r in pp.itertuples():
        west = r.side == "west"
        pad = (np.sqrt(dot_size(r.pop)) / 2 + 2) / 72 * PANEL_W_KM * 1000 / PANEL_W  # dot radius + 2pt, in metres
        texts.append(pax.text(r.geometry.x + (-pad if west else pad), r.geometry.y,
                              f"{SHORT.get(r.name.split(',')[0], r.name.split(',')[0])}\n{offset_label(r.tz)}", fontsize=6.2, color=INK,
                              ha="right" if west else "left", va="center", linespacing=1.15, zorder=5,
                              bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.75)))
    adjust_text(texts, ax=pax, x=pp.geometry.x.values, y=pp.geometry.y.values, expand=(1.1, 1.3),
                only_move={"text": "y", "static": "y", "explode": "y", "pull": "y"})
    pax.set_xlim(-hw, hw); pax.set_ylim(-hh, hh); pax.set_aspect("equal")
    pax.set_rasterization_zorder(2.5)
    pax.set_xticks([]); pax.set_yticks([]); pax.set_xlabel(""); pax.set_ylabel("")
    for s in pax.spines.values():
        s.set_color(TZ); s.set_linewidth(0.6)
    short = lambda s: s.replace("United States of America", "USA")
    borders = f"{', '.join(dict.fromkeys(sub.west_country.map(short)))} → {', '.join(dict.fromkeys(sub.east_country.map(short)))}"
    pax.set_title(f"{c['n']}  {borders}\n{sub.dist_km.iloc[0]:.0f} km apart", loc="left", fontsize=7,
                  color=INK, pad=3, linespacing=1.3)
    if idx == 0:  # scale bar, same for every panel
        x0, y0 = -hw + 15000, -hh + 18000
        pax.plot([x0, x0 + 100000], [y0, y0], color=INK, lw=1.5, solid_capstyle="butt", zorder=6)
        pax.text(x0 + 50000, y0 + 9000, "100 km", ha="center", va="bottom", fontsize=6, color=INK, zorder=6)

fig.text(MARGIN / FIG_W, 0.12 / FIG_H, f"All panels same scale ({PANEL_W_KM} × {PANEL_H_KM} km), local azimuthal equidistant projection; "
         "dark lines are time zone boundaries and coastlines, white lines country borders; km = distance between the two cities.\n"
         "City offsets shown as UTC winter (from 1 Nov 2026) / summer 2027. Panel dot size scales with metro population (Natural Earth POP_MAX).\n"
         "Data: Natural Earth v5.1.2; timezone-boundary-builder 2026e / IANA tzdata 2026e (© OpenStreetMap contributors, ODbL). "
         "World map: Equal Earth.", fontsize=7.5, color=INK2)
fig.savefig(f"output/map_inverted_pairs_with_panels{SUFFIX}.png", dpi=200, facecolor=SURFACE)
fig.savefig(f"output/map_inverted_pairs_with_panels{SUFFIX}.svg", dpi=200, facecolor=SURFACE)
