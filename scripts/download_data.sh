#!/usr/bin/env bash
# Fetch raw source data into data/raw/. Re-run to refresh; bump versions below.
set -euo pipefail
cd "$(dirname "$0")/.."

NE_VERSION=v5.1.2   # https://github.com/nvkelso/natural-earth-vector/tags
TZ_VERSION=2026e    # https://github.com/evansiroky/timezone-boundary-builder/releases

NE=data/raw/natural_earth; TZ=data/raw/timezones
mkdir -p "$NE" "$TZ"

# Natural Earth: official repo mirror (naciscdn.org is blocked in some environments)
for scale in 10m 50m; do
  for layer in admin_0_countries_lakes populated_places; do
    for ext in shp shx dbf prj cpg; do
      curl -sSfL -o "$NE/ne_${scale}_${layer}.${ext}" \
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/${NE_VERSION}/${scale}_cultural/ne_${scale}_${layer}.${ext}"
    done
  done
done

# Time zones: timezone-boundary-builder (built from OSM + IANA tzdata of the same version)
R=https://github.com/evansiroky/timezone-boundary-builder/releases/download/${TZ_VERSION}
for f in timezones-with-oceans-now.shapefile timezones-with-oceans-now.geojson timezones-with-oceans.shapefile; do
  curl -sSfL -o "$TZ/$f.zip" "$R/$f.zip"
  rm -rf "$TZ/$f" && unzip -oq "$TZ/$f.zip" -d "$TZ/$f"
done
curl -sSfL -o "$TZ/timezone-names.json" "$R/timezone-names.json"
