"""Write docs/index.html (the GitHub Pages site) from the final pair list."""
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd

WINTER, SUMMER = datetime(2026, 11, 1, 12), datetime(2027, 7, 15, 12)

pairs = pd.read_csv("output/inverted_pairs_100k_200km_ew50_per_border.csv")
pairs = pairs.assign(mid_lon=(pairs.west_lon + pairs.east_lon) / 2).sort_values("mid_lon").reset_index(drop=True)


def offset(tzid, when):
    return when.replace(tzinfo=ZoneInfo(tzid)).utcoffset().total_seconds() / 3600


def gap(h):
    """-1.0 -> '1 h behind', -0.25 -> '15 min behind', 0 -> 'same time'."""
    if h == 0:
        return "same time"
    hours, mins = divmod(round(abs(h) * 60), 60)
    text = " ".join(filter(None, [f"{hours} h" if hours else "", f"{mins} min" if mins else ""]))
    return f"{text} {'behind' if h < 0 else 'ahead'}"


rows = []
for i, r in pairs.iterrows():
    w, e = r.west.split(", "), r.east.split(", ")
    short = lambda c: c.replace("United States of America", "USA")
    rows.append(f"""      <tr>
        <td class="num">{i + 1}</td>
        <td>{escape(w[0])} <span class="cc">{escape(short(w[-1]))}</span></td>
        <td>{escape(e[0])} <span class="cc">{escape(short(e[-1]))}</span></td>
        <td class="num">{r.dist_km:.0f}&nbsp;km</td>
        <td class="num">{r.east_west_km:.0f}&nbsp;km</td>
        <td>{gap(offset(r.east_tz, WINTER) - offset(r.west_tz, WINTER))}</td>
        <td>{gap(offset(r.east_tz, SUMMER) - offset(r.west_tz, SUMMER))}</td>
      </tr>""")

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backwards Clocks</title>
<meta name="description" content="Nearby city pairs where the more easterly city keeps an earlier clock, from Vancouver and Seattle to Singapore and Tanjungpinang.">
<meta property="og:title" content="Backwards Clocks">
<meta property="og:description" content="Nearby cities where the eastern one is on an earlier clock.">
<meta property="og:image" content="map.png">
<style>
  :root {{
    --bg: #fcfcfb; --ink: #1d1c1a; --ink-2: #52514e; --rule: #e4e3df; --accent: #2a78d6;
    --winter: #eb6834; --summer: #1baf7a;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink);
         font: 17px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 1400px; margin: 0 auto; padding: 32px 16px 64px; }}
  .prose {{ max-width: 46rem; }}
  h1 {{ font-size: clamp(1.8rem, 4vw, 2.6rem); line-height: 1.15; margin: 0 0 .4em; letter-spacing: -0.01em; }}
  h2 {{ font-size: 1.25rem; margin: 2.2em 0 .5em; }}
  p {{ margin: 0 0 1em; }}
  .lede {{ font-size: 1.15rem; color: var(--ink-2); }}
  a {{ color: var(--accent); }}
  figure {{ margin: 28px 0 8px; }}
  figure img {{ width: 100%; height: auto; display: block; border: 1px solid var(--rule); }}
  figcaption {{ font-size: .85rem; color: var(--ink-2); margin-top: 8px; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; font-size: .92rem; min-width: 640px; }}
  th, td {{ text-align: left; padding: 6px 14px 6px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }}
  th {{ font-weight: 600; color: var(--ink-2); font-size: .8rem; text-transform: uppercase; letter-spacing: .03em; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .cc {{ color: var(--ink-2); font-size: .85em; }}
  ul {{ padding-left: 1.2em; }}
  li {{ margin-bottom: .4em; }}
  footer {{ margin-top: 3em; font-size: .85rem; color: var(--ink-2); }}
</style>
</head>
<body>
<main>
  <div class="prose">
    <h1>Backwards clocks</h1>
    <p class="lede">From 1&nbsp;November&nbsp;2026, driving from Seattle to Vancouver takes you about 200&nbsp;km north and
      60&nbsp;km <em>west</em>&nbsp;— yet you set your watch an hour <em>ahead</em>, as if you'd travelled east.</p>
    <p>British Columbia stopped changing its clocks in 2026 and now stays on UTC−7 all year, while Washington State still
      falls back to UTC−8 each winter. So from November to March, Seattle is an hour behind its neighbour to the
      north-west. How unusual is that? This map finds every pair of nearby cities in the world where the more easterly
      one keeps the earlier clock.</p>
  </div>

  <figure>
    <a href="map.png"><img src="map.png" alt="World map in the Equal Earth projection with time zones shaded from violet in the west to rose in the east, marking 18 nearby city pairs where the eastern city's clock is behind, with 18 zoomed panels below showing each pair, its time zone boundary and both cities' UTC offsets." width="3200" height="2479"></a>
    <figcaption>Click for the full-size image. Also available as <a href="map.svg">SVG</a>.</figcaption>
  </figure>

  <h2>The 18 pairs</h2>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th class="num">#</th><th>Western city</th><th>Eastern city</th><th class="num">Apart</th>
        <th class="num">Further east</th><th>Eastern clock, winter</th><th>Eastern clock, summer</th>
      </tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
  </div>
  <p class="cc">“Winter” is from 1&nbsp;Nov&nbsp;2026 and “summer” is July&nbsp;2027, both in the northern hemisphere.
    <a href="city_pairs.csv">Download the pairs as CSV.</a></p>

  <div class="prose">
    <h2>How the pairs were chosen</h2>
    <p>The thresholds are anchored on Seattle and Vancouver, so every pair shown is at least as striking a case:</p>
    <ul>
      <li><strong>Close together:</strong> no more than 200&nbsp;km apart on the globe (Seattle–Vancouver: 196&nbsp;km).</li>
      <li><strong>Clearly east:</strong> the eastern city is at least 50&nbsp;km further east (Seattle: 60&nbsp;km).</li>
      <li><strong>Backwards:</strong> the eastern city's clock is behind the western one's, in winter, summer or both.</li>
      <li><strong>Real cities:</strong> both have a metro population of at least 100,000.</li>
      <li><strong>One per border:</strong> where several pairs share a border, only the one with the largest smaller city is shown.</li>
    </ul>
    <p>Each city was placed in its time zone using the boundary polygons, and clock offsets come from the IANA time zone
      database, release 2026e. That release includes 2026's Canadian changes: British Columbia, Alberta, the Northwest
      Territories and Manitoba all moved to permanent time. Distances are measured on the WGS84 ellipsoid.</p>
    <p>Caveats: Natural Earth's list of populated places is chosen for cartography and isn't a complete census of every
      city over 100,000, so some pairs may be missing. Time zones follow the IANA database and OpenStreetMap, which may
      differ from local practice in disputed or occupied areas.</p>

    <h2>Data</h2>
    <ul>
      <li>Countries and populated places: <a href="https://www.naturalearthdata.com/">Natural Earth</a> v5.1.2 (public domain).</li>
      <li>Time zone boundaries: <a href="https://github.com/evansiroky/timezone-boundary-builder">timezone-boundary-builder</a>
        2026e, © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, available under the
        <a href="https://opendatacommons.org/licenses/odbl/">Open Database License</a>.</li>
      <li>UTC offsets: <a href="https://www.iana.org/time-zones">IANA time zone database</a> 2026e.</li>
    </ul>
  </div>

  <footer>Map made with Python (geopandas, pyproj, matplotlib). World map: Equal Earth projection; panels: local azimuthal
    equidistant, all at the same scale.</footer>
</main>
</body>
</html>
"""
open("docs/index.html", "w").write(html)
print(f"wrote docs/index.html ({len(pairs)} pairs)")
