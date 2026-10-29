"""World map (Equal Earth) of inverted time-zone city pairs.

Filters: both cities POP_MAX >= 100k, <= 200 km apart, east city >= 50 km further east,
east city's clock behind the west city's in Jan and/or Jul 2027 (tzdata 2026e).
"""
import sys

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import LineString, Point
from pyproj import Geod

CRS = "EPSG:8857"  # Equal Earth (Greenwich)
MIN_EW_KM = 50
ONE_PER_BORDER = "--one-per-border" in sys.argv  # keep the pair with the largest smaller city per country pair

COLORS = {"jan,jul": "#2a78d6", "jan": "#eb6834", "jul": "#1baf7a"}  # dataviz reference slots 1-3
LABELS = {"jan,jul": "East city behind all year", "jan": "Behind in Jan only (northern winter)",
          "jul": "Behind in Jul only (northern summer)"}
SURFACE, LAND, BORDER, TZ, INK, INK2 = "#fcfcfb", "#e4e3df", "#fcfcfb", "#b9b8b2", "#0b0b0b", "#52514e"

pairs = pd.read_csv("output/inverted_pairs_100k_200km.csv")
pairs = pairs[pairs.east_west_km >= MIN_EW_KM].copy()
pairs.to_csv(f"output/inverted_pairs_100k_200km_ew{MIN_EW_KM}.csv", index=False)
suffix = ""
if ONE_PER_BORDER:
    pairs["border"] = pairs.west_country + " → " + pairs.east_country
    pairs["min_pop"] = pairs[["west_pop", "east_pop"]].min(axis=1)
    pairs = pairs.loc[pairs.groupby("border").min_pop.idxmax()]
    suffix = "_per_border"
    pairs.to_csv(f"output/inverted_pairs_100k_200km_ew{MIN_EW_KM}{suffix}.csv", index=False)

geod = Geod(ellps="WGS84")
def geodesic(r, n=16):
    mid = geod.npts(r.west_lon, r.west_lat, r.east_lon, r.east_lat, n)
    return LineString([(r.west_lon, r.west_lat), *mid, (r.east_lon, r.east_lat)])

lines = gpd.GeoDataFrame(pairs, geometry=[geodesic(r) for r in pairs.itertuples()], crs=4326).to_crs(CRS)
pts = pd.concat([pairs[["west", "west_lon", "west_lat", "inverted_in"]].set_axis(["name", "lon", "lat", "k"], axis=1),
                 pairs[["east", "east_lon", "east_lat", "inverted_in"]].set_axis(["name", "lon", "lat", "k"], axis=1)])
pts = pts.drop_duplicates("name")
pts = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326).to_crs(CRS)

land = gpd.read_file("data/raw/natural_earth/ne_50m_admin_0_countries_lakes.shp").to_crs(CRS)
tz = gpd.read_file("data/raw/timezones/timezones-with-oceans-now.shapefile/combined-shapefile-with-oceans-now.shp")
tz_lines = tz.boundary.clip_by_rect(-179.99, -89.99, 179.99, 89.99).segmentize(0.5).to_crs(CRS)  # densify so meridians curve

# outline of the globe in Equal Earth
edge = [(-180, y) for y in range(-90, 91)] + [(180, y) for y in range(90, -91, -1)]
globe = gpd.GeoSeries([LineString(edge + [edge[0]])], crs=4326).to_crs(CRS)
globe_poly = gpd.GeoSeries([gpd.GeoSeries([LineString(edge)], crs=4326).to_crs(CRS).iloc[0].convex_hull], crs=CRS)

fig, ax = plt.subplots(figsize=(16, 8.6), facecolor=SURFACE)
ax.set_facecolor(SURFACE)
globe_poly.plot(ax=ax, color="#f1f4f6", zorder=0)
land.plot(ax=ax, color=LAND, edgecolor=BORDER, linewidth=0.4, zorder=1)
tz_lines.clip(globe_poly.iloc[0]).plot(ax=ax, color=TZ, linewidth=0.35, zorder=2)
globe.plot(ax=ax, color=TZ, linewidth=0.6, zorder=2)
for k, c in COLORS.items():
    lines[lines.inverted_in == k].plot(ax=ax, color=c, linewidth=1.6, zorder=3)
    p = pts[pts.k == k]
    ax.scatter(p.geometry.x, p.geometry.y, s=14, color=c, edgecolor=SURFACE, linewidth=0.6, zorder=4,
               label=f"{LABELS[k]} ({(n := (pairs.inverted_in == k).sum())} pair{'' if n == 1 else 's'})")

ax.set_axis_off(); ax.set_aspect("equal")
ax.legend(loc="lower left", bbox_to_anchor=(0, -0.10), ncol=3, frameon=False, fontsize=10, labelcolor=INK2, markerscale=1.6)
ax.set_title("Nearby cities where the eastern one is on an earlier clock",
             loc="left", fontsize=16, color=INK, pad=14, fontweight="bold")
ax.text(0, 1.0, f"{len(pairs)} city pairs{' (largest per border)' if ONE_PER_BORDER else ''}, ≤200 km apart, eastern city ≥{MIN_EW_KM} km further east, both ≥100k people. "
        "Gray lines: time zone boundaries.", transform=ax.transAxes, fontsize=10, color=INK2, va="bottom")
fig.text(0.01, 0.01, "Data: Natural Earth v5.1.2; timezone-boundary-builder 2026e / IANA tzdata 2026e (© OpenStreetMap contributors, ODbL). "
         "Equal Earth projection.", fontsize=8, color=INK2)
fig.savefig(f"output/map_world_inverted_pairs{suffix}.png", dpi=200, bbox_inches="tight", facecolor=SURFACE)
fig.savefig(f"output/map_world_inverted_pairs{suffix}.svg", bbox_inches="tight", facecolor=SURFACE)
