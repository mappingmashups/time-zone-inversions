#!/usr/bin/env bash
# Rebuild everything from raw data: analysis CSVs, maps, and the GitHub Pages copy in docs/.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/bin/python}

[ -d data/raw/timezones ] || scripts/download_data.sh
mkdir -p output docs
"$PY" analysis/inverted_pairs.py 100000 200        # all nearby pairs + inverted pairs
"$PY" analysis/map_world.py --one-per-border       # 50 km east-west filter, largest pair per border
"$PY" analysis/map_with_insets.py                  # final map
cp output/map_inverted_pairs_with_panels.png docs/map.png
cp output/map_inverted_pairs_with_panels.svg docs/map.svg
cp output/inverted_pairs_100k_200km_ew50_per_border.csv docs/city_pairs.csv
"$PY" analysis/make_page.py                         # docs/index.html
