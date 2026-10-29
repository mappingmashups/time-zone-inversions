"""Find nearby major-city pairs on opposite sides of a time zone boundary where
the more easterly city's clock is *behind* the more westerly one (an "inverted" pair).

Usage: python analysis/inverted_pairs.py [MIN_POP] [MAX_KM]   (defaults 2,000,000 and 200)
Offsets evaluated with IANA tzdata (pip tzdata) on a winter and a summer date.
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import geopandas as gpd
import numpy as np
import pandas as pd
import tzdata
from pyproj import Geod

POP_MIN = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
MAX_KM = int(sys.argv[2]) if len(sys.argv) > 2 else 200
DATES = {"jan": datetime(2027, 1, 15, 12), "jul": datetime(2027, 7, 15, 12)}

places = gpd.read_file("data/raw/natural_earth/ne_10m_populated_places.shp")
zones = gpd.read_file("data/raw/timezones/timezones-with-oceans.shapefile/combined-shapefile-with-oceans.shp")

cities = places.loc[places.POP_MAX >= POP_MIN, ["NAME", "ADM0NAME", "ADM1NAME", "POP_MAX", "TIMEZONE", "geometry"]]
cities = gpd.sjoin(cities, zones, how="left", predicate="within").drop(columns="index_right")
cities = cities[~cities.index.duplicated()]  # guard against overlap zones
assert cities.tzid.notna().all()

def utc_offset_h(tzid, when):
    return when.replace(tzinfo=ZoneInfo(tzid)).utcoffset().total_seconds() / 3600

for k, when in DATES.items():
    cities[f"off_{k}"] = [utc_offset_h(t, when) for t in cities.tzid]

# candidate pairs via vectorized haversine (generous margin), then exact geodesic distance
lon, lat = np.radians(cities.geometry.x.values), np.radians(cities.geometry.y.values)
i, j = np.triu_indices(len(cities), k=1)
h = np.sin((lat[j] - lat[i]) / 2) ** 2 + np.cos(lat[i]) * np.cos(lat[j]) * np.sin((lon[j] - lon[i]) / 2) ** 2
near = 2 * 6371 * np.arcsin(np.sqrt(h)) <= MAX_KM * 1.01
i, j = i[near], j[near]

geod = Geod(ellps="WGS84")
rows = []
for ai, bi in zip(i, j):
    a, b = cities.iloc[ai], cities.iloc[bi]
    _, _, d = geod.inv(a.geometry.x, a.geometry.y, b.geometry.x, b.geometry.y)
    if d / 1000 > MAX_KM:
        continue
    # order so that `e` is the more easterly city (signed dlon, antimeridian-safe)
    dlon = (b.geometry.x - a.geometry.x + 180) % 360 - 180
    w, e = (a, b) if dlon >= 0 else (b, a)
    dlon = abs(dlon)
    ew_km = np.radians(dlon) * 6371 * np.cos(np.radians((a.geometry.y + b.geometry.y) / 2))
    r = dict(west=f"{w.NAME}, {w.ADM0NAME}", east=f"{e.NAME}, {e.ADM0NAME}",
             west_tz=w.tzid, east_tz=e.tzid, dist_km=round(d / 1000, 1),
             east_west_km=round(ew_km, 1), north_south_km=round(abs(a.geometry.y - b.geometry.y) * 111.2, 1),
             west_pop=int(w.POP_MAX), east_pop=int(e.POP_MAX),
             west_lon=w.geometry.x, west_lat=w.geometry.y, east_lon=e.geometry.x, east_lat=e.geometry.y)
    for k in DATES:
        # positive = east city ahead (expected); negative = east city behind (inverted)
        r[f"east_minus_west_h_{k}"] = e[f"off_{k}"] - w[f"off_{k}"]
    rows.append(r)

pairs = pd.DataFrame(rows)
diffcols = [f"east_minus_west_h_{k}" for k in DATES]
pairs["cross_boundary"] = (pairs[diffcols] != 0).any(axis=1)
pairs["inverted_in"] = pairs.apply(lambda r: ",".join(k for k in DATES if r[f"east_minus_west_h_{k}"] < 0), axis=1)
pairs = pairs.sort_values(["inverted_in", "dist_km"], ascending=[False, True])

print(f"tzdata {tzdata.IANA_VERSION}; {len(cities)} cities >= {POP_MIN:,}; "
      f"{len(pairs)} pairs within {MAX_KM} km; {pairs.cross_boundary.sum()} cross a boundary; "
      f"{(pairs.inverted_in != '').sum()} inverted")
show = ["west", "east", "west_tz", "east_tz", "dist_km", "east_west_km", *diffcols, "inverted_in"]
print(pairs.loc[pairs.inverted_in != "", show].to_string(index=False))
tag = f"{POP_MIN // 1000}k_{MAX_KM}km"
pairs.to_csv(f"output/city_pairs_{tag}.csv", index=False)
cities.drop(columns="geometry").assign(lon=cities.geometry.x, lat=cities.geometry.y).to_csv(f"output/cities_{POP_MIN // 1000}k.csv", index=False)
