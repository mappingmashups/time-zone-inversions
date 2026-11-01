"""Shared data loading, styling and drawing for the time-zone-inversion maps.

Used by map_with_insets.py (the main figure) and social_cards.py (square images).
"""
import math
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import shapely
from adjustText import adjust_text
from pyproj import Geod, Transformer
from shapely.geometry import LineString, box

WORLD_CRS = "EPSG:8857"  # Equal Earth
# simplification tolerances (metres), ~0.1 pt at print size: keeps the SVG light without visible change
WORLD_TOL, PANEL_TOL = 3000, 300
PAIR_INK = "#34322e"  # world-map dots and links: one neutral colour

COLORS = {"jan,jul": "#2a78d6", "jan": "#eb6834", "jul": "#1baf7a"}  # dataviz reference slots 1-3
LABELS = {"jan,jul": "All year", "jan": "Northern winter only",
          "jul": "Northern summer only"}
SURFACE, OCEAN, LAND, TZ, TZ_STRONG, INK, INK2 = "#fcfcfb", "#f1f4f6", "#e4e3df", "#b9b8b2", "#52514e", "#0b0b0b", "#52514e"
SHORT = {"Pedro Juan Caballero": "Pedro Juan\nCaballero"}  # wrap long labels in the small panels
OCEAN_FADE = dict(color=OCEAN, alpha=0.85, edgecolor="none")  # mutes time zone colors at sea

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


def geodesic(r, n=16):
    mid = geod.npts(r.west_lon, r.west_lat, r.east_lon, r.east_lat, n)
    return LineString([(r.west_lon, r.west_lat), *mid, (r.east_lon, r.east_lat)])


def load():
    """Pairs, city points, pair lines and the base layers, ready to draw."""
    pairs = pd.read_csv("output/inverted_pairs_100k_200km_ew50_per_border.csv")
    pairs = pairs.assign(mid_lon=(pairs.west_lon + pairs.east_lon) / 2).sort_values("mid_lon").reset_index(drop=True)
    pairs["n"] = pairs.index + 1  # panel numbers, west to east

    land50 = gpd.read_file("data/raw/natural_earth/ne_50m_admin_0_countries_lakes.shp")
    land10 = gpd.read_file("data/raw/natural_earth/ne_10m_admin_0_countries_lakes.shp")
    tz_now = gpd.read_file("data/raw/timezones/timezones-with-oceans-now.shapefile/combined-shapefile-with-oceans-now.shp")
    # The "now" layer leaves zones that changed rules during 2026 unmerged (e.g. America/Edmonton vs America/Regina,
    # both permanent UTC-6). Merge every zone whose clock matches on the 1st and 15th of each month, Nov 2026 -
    # Oct 2028, so boundaries are drawn only where the clock actually differs.
    samples = [datetime(2026 + (10 + m) // 12, (10 + m) % 12 + 1, d, 12) for m in range(24) for d in (1, 15)]
    tz_now["clock"] = [tuple(t.replace(tzinfo=ZoneInfo(z)).utcoffset().total_seconds() for t in samples)
                       for z in tz_now.tzid]
    tz_now = tz_now.set_geometry(tz_now.geometry.make_valid()).dissolve(by="clock", as_index=False, aggfunc="first")
    tz_edges = tz_now.boundary.clip_by_rect(-179.99, -89.99, 179.99, 89.99)
    tz_now["offset"] = [DATES["jan"].replace(tzinfo=ZoneInfo(t)).utcoffset().total_seconds() / 3600 for t in tz_now.tzid]
    tz_now["fill"] = tz_now.offset.map(zone_fill)
    print(f"{len(tz_now)} clock zones after merging")

    lines = gpd.GeoDataFrame(pairs, geometry=[geodesic(r) for r in pairs.itertuples()], crs=4326)
    pts = pd.concat([pairs[[f"{s}", f"{s}_lon", f"{s}_lat", f"{s}_tz", f"{s}_pop", "inverted_in"]]
                     .set_axis(["name", "lon", "lat", "tz", "pop", "k"], axis=1).assign(side=s)
                     for s in ("west", "east")]).drop_duplicates("name")
    pts = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326)
    return SimpleNamespace(pairs=pairs, pts=pts, lines=lines, land50=land50, land10=land10,
                           tz_now=tz_now, tz_edges=tz_edges)


def world_frame(south_lat=-57):
    """Equal Earth outline cropped just south of Cape Horn (no Antarctica): (shape, (x0, y0, x1, y1))."""
    edge = [(-180, y) for y in range(-90, 91)] + [(180, y) for y in range(90, -91, -1)]
    globe_poly = gpd.GeoSeries([LineString(edge)], crs=4326).to_crs(WORLD_CRS).iloc[0].convex_hull
    y_south = Transformer.from_crs(4326, WORLD_CRS, always_xy=True).transform(0, south_lat)[1]
    gx0, _, gx1, gy1 = globe_poly.bounds
    return globe_poly.intersection(box(gx0, y_south, gx1, gy1)), (gx0, y_south, gx1, gy1)


def draw_world(ax, d, scale=1.0, numbers=True, number_size=9):
    """Time zone base map plus haloed pair markers on an Equal Earth axes. `scale` multiplies line/dot sizes."""
    map_shape, (gx0, y_south, gx1, gy1) = world_frame()
    ax.set_facecolor(SURFACE)
    wz = d.tz_now.set_geometry(d.tz_now.geometry.segmentize(0.5)).to_crs(WORLD_CRS)
    wz = wz.set_geometry(wz.geometry.simplify(WORLD_TOL).make_valid()).clip(map_shape)
    wz.plot(ax=ax, color=wz.fill, edgecolor="none", zorder=0)
    wland_raw = d.land50[d.land50.ADM0_A3 != "ATA"].to_crs(WORLD_CRS)
    wland_raw = wland_raw.set_geometry(wland_raw.geometry.make_valid())
    # union BEFORE simplifying: countries simplified one by one no longer share edges exactly, and the
    # hairline gaps between them would otherwise be drawn as dark "coastline" inside the continents
    wland_union = shapely.make_valid(wland_raw.union_all().simplify(WORLD_TOL)).intersection(map_shape)
    wland = wland_raw.set_geometry(wland_raw.geometry.simplify(WORLD_TOL).make_valid()).clip(map_shape)  # white borders
    wedges = d.tz_edges.segmentize(0.5).to_crs(WORLD_CRS).simplify(WORLD_TOL).clip(map_shape)
    wedges.plot(ax=ax, color=TZ_STRONG, alpha=0.35, linewidth=0.3 * scale, zorder=0.5)  # at sea: faded by the mask
    gpd.GeoSeries([map_shape.difference(wland_union)], crs=WORLD_CRS).plot(ax=ax, **OCEAN_FADE, zorder=1)
    wland.boundary.plot(ax=ax, color="white", linewidth=0.35 * scale, zorder=1.5)
    wedges.intersection(wland_union).plot(ax=ax, color=TZ_STRONG, alpha=0.6, linewidth=0.4 * scale, zorder=1.7)
    coast = wland_union.boundary.difference(map_shape.boundary.buffer(5000))  # drop artificial edges at the frame
    gpd.GeoSeries([coast], crs=WORLD_CRS).plot(ax=ax, color=TZ_STRONG, alpha=0.6, linewidth=0.4 * scale, zorder=1.7)
    gpd.GeoSeries([map_shape.boundary], crs=WORLD_CRS).plot(ax=ax, color=TZ, linewidth=0.6 * scale, zorder=2)
    wpts = d.pts.to_crs(WORLD_CRS)
    wlines = d.lines.to_crs(WORLD_CRS)
    # pass 1: one shared outline layer (lines + dots) so nearby pairs merge into a single haloed blob
    dot, line, halo = 6.5 * scale, 2.4 * scale, 1.6 * scale  # dot diameter, line width, outline width (pt)
    wlines.plot(ax=ax, color=SURFACE, linewidth=line + 2 * halo, zorder=3.5, capstyle="round")
    ax.scatter(wpts.geometry.x, wpts.geometry.y, s=(dot + 2 * halo) ** 2, color=SURFACE, linewidth=0, zorder=3.5)
    # pass 2: lines and dots on top in a single ink, no individual edges (season colour lives in the panels)
    wlines.plot(ax=ax, color=PAIR_INK, linewidth=line, zorder=3.8)
    ax.scatter(wpts.geometry.x, wpts.geometry.y, s=dot ** 2, color=PAIR_INK, linewidth=0, zorder=4)
    if numbers:
        wt = Transformer.from_crs(4326, WORLD_CRS, always_xy=True)
        texts = []
        for r in d.pairs.itertuples():
            x, y = wt.transform((r.west_lon + r.east_lon) / 2, (r.west_lat + r.east_lat) / 2)
            texts.append(ax.text(x, y, str(r.n), fontsize=number_size, fontweight="bold", color=INK, zorder=5,
                                 ha="center", va="center"))
        adjust_text(texts, ax=ax, x=wpts.geometry.x.values, y=wpts.geometry.y.values, expand=(2.4, 2.4),
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5), min_arrow_len=4)
    ax.set_xlim(gx0, gx1); ax.set_ylim(y_south, gy1)
    ax.set_rasterization_zorder(2.5)  # base map (z < 2.5) becomes an image in the SVG; symbols and text stay vector
    ax.set_axis_off(); ax.set_aspect("equal")


def draw_zone_key(ax, rect, fontsize=7, title="Time zone: UTC offset from 1 Nov 2026"):
    """Colour ramp for the zone fills, on a light backing, placed at `rect` (axes fraction)."""
    x, y, w, h = rect
    bg = ax.inset_axes([x - 0.01, y - 0.035, w + 0.02, h + 0.063])
    bg.set_facecolor(SURFACE); bg.patch.set_alpha(0.85); bg.set_xticks([]); bg.set_yticks([])
    for sp in bg.spines.values():
        sp.set_visible(False)
    kax = ax.inset_axes(rect)
    kax.imshow([[matplotlib.colors.to_rgb(zone_fill(o)) for o in range(-12, 15)]], aspect="auto",
               extent=(-12.5, 14.5, 0, 1))
    kax.set_yticks([]); kax.set_xticks([-12, -6, 0, 6, 12])
    kax.set_xticklabels(["−12", "−6", "0", "+6", "+12"], fontsize=fontsize, color=INK2)
    kax.tick_params(length=2, color=INK2, pad=1)
    for sp in kax.spines.values():
        sp.set_visible(False)
    kax.set_title(title, fontsize=fontsize + 0.5, color=INK2, loc="left", pad=3)


def draw_panel(pax, d, i, w_km, h_km, w_in, label_size=6.2, dot_scale=1.0, line_width=1.3, line_scale=1.0,
               scale_bar=False, title=True, title_size=7, title_one_line=False):
    """Zoomed same-scale map of pair i (row index into d.pairs) in a local azimuthal equidistant projection.

    w_km x h_km is the ground extent, w_in the axes width in inches (to place labels clear of the dots).
    """
    r0 = d.pairs.loc[i]
    lon0, lat0 = (r0.west_lon + r0.east_lon) / 2, (r0.west_lat + r0.east_lat) / 2
    crs = aeqd(lon0, lat0)
    hw, hh = w_km * 500, h_km * 500
    # generous lon/lat window for clipping before projecting
    dlat = h_km / 111 * 0.9 + 1
    dlon = w_km / (111 * math.cos(math.radians(min(abs(lat0) + dlat, 85)))) * 0.9 + 1
    win = box(lon0 - dlon, lat0 - dlat, lon0 + dlon, lat0 + dlat)
    frame = box(-hw, -hh, hw, hh)
    pz = d.tz_now.clip(win)
    pz = pz.set_geometry(pz.geometry.segmentize(0.05)).to_crs(crs)
    pz = pz.set_geometry(pz.geometry.simplify(PANEL_TOL).make_valid()).clip(frame)
    pz.plot(ax=pax, color=pz.fill, edgecolor="none", zorder=0)
    pland_raw = d.land10.clip(win).to_crs(crs)
    pland_raw = pland_raw.set_geometry(pland_raw.geometry.make_valid())
    pland_union = shapely.make_valid(pland_raw.union_all().simplify(PANEL_TOL)).intersection(frame)  # see draw_world
    pland = pland_raw.set_geometry(pland_raw.geometry.simplify(PANEL_TOL).make_valid()).clip(frame)
    pedges = gpd.GeoSeries([d.tz_edges.clip(win).union_all()], crs=4326).segmentize(0.05).to_crs(crs) \
        .simplify(PANEL_TOL).clip(frame)
    pedges.plot(ax=pax, color=TZ_STRONG, linewidth=0.8 * line_scale, zorder=0.5)
    sea = frame.difference(pland_union)
    if not sea.is_empty:
        gpd.GeoSeries([sea], crs=crs).plot(ax=pax, **OCEAN_FADE, zorder=1)
    pland.boundary.plot(ax=pax, color="white", linewidth=0.8 * line_scale, zorder=1.5)
    pcoast = pland_union.boundary.difference(frame.boundary.buffer(500))
    if not pcoast.is_empty:
        gpd.GeoSeries([pcoast], crs=crs).plot(ax=pax, color=TZ_STRONG, linewidth=0.6 * line_scale, zorder=1.7)
    on_land = pedges.intersection(pland_union)
    on_land = on_land[~on_land.is_empty]
    if len(on_land):
        on_land.plot(ax=pax, color=TZ_STRONG, linewidth=0.8 * line_scale, zorder=1.7)  # time zone line wins over border
    d.lines.loc[[i]].to_crs(crs).plot(ax=pax, color=COLORS[r0.inverted_in], linewidth=line_width, zorder=3)
    pp = d.pts[d.pts.name.isin({r0.west, r0.east})].to_crs(crs)
    pp = pp.sort_values("pop", ascending=False)  # small dot on top if they overlap
    pax.scatter(pp.geometry.x, pp.geometry.y, s=dot_size(pp["pop"]) * dot_scale ** 2, color=[COLORS[k] for k in pp.k],
                edgecolor=SURFACE, linewidth=0.8 * dot_scale, zorder=4)
    texts = []
    for r in pp.itertuples():
        west = r.side == "west"
        # dot radius + 2pt, in metres
        pad = (np.sqrt(dot_size(r.pop)) * dot_scale / 2 + 2) / 72 * w_km * 1000 / w_in
        name = r.name.split(",")[0]
        texts.append(pax.text(r.geometry.x + (-pad if west else pad), r.geometry.y,
                              f"{SHORT.get(name, name)}\n{offset_label(r.tz)}", fontsize=label_size, color=INK,
                              ha="right" if west else "left", va="center", linespacing=1.15, zorder=5,
                              bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.75)))
    adjust_text(texts, ax=pax, x=pp.geometry.x.values, y=pp.geometry.y.values, expand=(1.1, 1.3),
                only_move={"text": "y", "static": "y", "explode": "y", "pull": "y"})
    pax.set_xlim(-hw, hw); pax.set_ylim(-hh, hh); pax.set_aspect("equal")
    pax.set_rasterization_zorder(2.5)
    pax.set_xticks([]); pax.set_yticks([]); pax.set_xlabel(""); pax.set_ylabel("")
    for s in pax.spines.values():
        s.set_color(TZ); s.set_linewidth(0.6)
    if title:
        short = lambda s: s.replace("United States of America", "USA")
        names = f"{r0.n}  {short(r0.west_country)} → {short(r0.east_country)}"
        if title_one_line:  # countries left, distance right
            pax.set_title(names, loc="left", fontsize=title_size, color=INK, pad=3)
            pax.set_title(f"{r0.dist_km:.0f} km", loc="right", fontsize=title_size, color=INK2, pad=3)
        else:
            pax.set_title(f"{names}\n{r0.dist_km:.0f} km apart", loc="left", fontsize=title_size, color=INK, pad=3,
                          linespacing=1.3)
    if scale_bar:  # 100 km, same for every panel at this scale
        x0, y0 = -hw + w_km * 34, -hh + h_km * 53
        pax.plot([x0, x0 + 100000], [y0, y0], color=INK, lw=1.5, solid_capstyle="butt", zorder=6)
        pax.text(x0 + 50000, y0 + h_km * 26, "100 km", ha="center", va="bottom", fontsize=label_size - 0.2,
                 color=INK, zorder=6)
