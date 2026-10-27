# Geospatial data: vectors, rasters and coordinate systems

Read this when data has locations: points, lines, polygons, addresses, boundaries, satellite or aerial imagery, elevation models, or gridded fields; and when maps or spatial joins are involved. Spatial SQL in PostgreSQL uses PostGIS (`postgresql.md`); land-cover classification and other models on imagery belong to `../../ml-engineering/GUIDE.md`.

## The stack

| Task | Tools |
|---|---|
| Vector data in Python | GeoPandas 1.x (on Shapely 2, pyogrio for I/O, pyproj for coordinates) |
| Raster data in Python | rasterio; rioxarray and Xarray for labeled, multi-band or time-series rasters; Dask for larger than memory |
| Command-line conversion and reprojection | GDAL and OGR (`ogrinfo`, `ogr2ogr`, `gdalinfo`, `gdalwarp`, `gdal_translate`) |
| Spatial SQL | PostGIS; DuckDB's spatial extension for files |
| Visual checks and editing | QGIS; `gdf.explore()` for an interactive web map in a notebook |
| Finding imagery | STAC catalogs and APIs (`pystac-client`) |

GeoPandas 1.0 (June 2024) made pyogrio the default I/O engine, requires Shapely 2, and finalized renames such as `sjoin(predicate=...)` (formerly `op=`). Check `geopandas.show_versions()`; it also prints the GDAL and PROJ versions underneath, which decide what formats and transformations are available.

## Coordinate reference systems

Most geospatial bugs are CRS bugs.

- **Geographic** CRSs (EPSG:4326, WGS 84) use degrees of latitude and longitude. **Projected** CRSs (UTM zones, national grids, equal-area projections) use metres or feet on a plane.
- `set_crs` declares what the coordinates already are (metadata only); `to_crs` transforms them. Setting the wrong CRS moves nothing but makes every later step wrong; transforming without a CRS set fails.
- Never compute areas, lengths, buffers or distances in degrees. Use a projected CRS suited to the purpose:

  ```python
  utm = gdf.estimate_utm_crs()                         # local conformal CRS for distances and buffers
  gdf_m = gdf.to_crs(utm)
  gdf_m["buffer_500m"] = gdf_m.buffer(500)
  area_km2 = gdf.to_crs("EPSG:6933").area / 1e6        # equal-area CRS for areas across large regions
  ```

  For a few long distances, geodesic computation on the ellipsoid (`pyproj.Geod(ellps="WGS84").inv(...)`) is exact and needs no projection.
- **Web Mercator** (EPSG:3857) is for map tiles. Its areas grow with latitude (Greenland looks the size of Africa); never measure in it.
- **Axis order:** EPSG:4326 formally lists latitude first, while most software and GeoJSON use longitude, latitude. Use `pyproj.Transformer.from_crs(src, dst, always_xy=True)`, and check a known point after any transformation.
- **Datums:** NAD83, ETRS89 and WGS 84 differ by up to a couple of metres and drift over time; high-accuracy work needs the right transformation, which PROJ may download as grid files. In offline environments, missing grids silently fall back to less accurate transformations; check `pyproj` network settings and log which transformation was used.
- Print `gdf.crs` after every read, join and transformation while developing. Two layers in different CRSs produce empty joins, not errors.

## Formats and I/O

| Format | Notes |
|---|---|
| GeoPackage (`.gpkg`) | SQLite-based single file, many layers, no field-name limits; the default choice for exchange |
| GeoParquet | Columnar and fast; best for large vector data in analytical pipelines (`gdf.to_parquet`, `gpd.read_parquet`); version 1.1 adds bounding-box columns for spatial filtering |
| FlatGeobuf | Streamable, spatially indexed, good for web delivery |
| GeoJSON | Text, human-readable; the RFC 7946 version requires WGS 84 longitude, latitude; large files are slow and imprecise if coordinates are rounded |
| Shapefile | Legacy: several sidecar files, 10-character field names, 2 GB limit, one geometry type per file, encoding often unspecified. Convert on arrival |
| GeoTIFF and Cloud-Optimized GeoTIFF (COG) | Raster standard; COGs are tiled with overviews so clients read only the needed window over HTTP |

Read only what you need: `gpd.read_file(path, bbox=(xmin, ymin, xmax, ymax), columns=[...], where="pop > 1000")` with pyogrio, or filtered GeoParquet reads.

## Vector operations

```python
import geopandas as gpd

points = gpd.read_parquet("incidents.parquet").to_crs(3035)      # a projected CRS for Europe
areas = gpd.read_file("districts.gpkg").to_crs(3035)

joined = gpd.sjoin(points, areas[["district_id", "geometry"]], how="left", predicate="within")
unmatched = joined["district_id"].isna().sum()
dupes = joined.index.duplicated().sum()          # points matched to more than one polygon
counts = joined.groupby("district_id").size().rename("incidents")
rates = areas.set_index("district_id").join(counts).assign(per_km2=lambda d: d.incidents / (d.area / 1e6))
```

- **Choose the predicate on purpose:** `within` excludes points exactly on a boundary, `intersects` includes them and can match a point to two neighboring polygons. Check for duplicated left indexes after the join, as above.
- `sjoin_nearest(..., max_distance=...)` in a projected CRS for "closest feature" questions; it returns ties as extra rows.
- `overlay` (intersection, union, difference), `dissolve` (merge by attribute with aggregation), `clip`, and `buffer` cover most polygon work. Overlay on large layers is slow; filter with the spatial index first.
- The spatial index (`gdf.sindex.query(geom, predicate="intersects")`) makes candidate searches fast; GeoPandas uses it inside joins automatically.
- **Invalid geometries** (self-intersections, unclosed rings) make operations fail or return wrong areas. Check `~gdf.is_valid` and `shapely.is_valid_reason`, repair with `make_valid()`, and count what changed.
- Shapely 2 functions are vectorized over arrays; avoid `apply` with a Python function per geometry.

## Rasters

```python
import rasterio
from rasterio.windows import from_bounds

with rasterio.open("dem.tif") as src:
    print(src.crs, src.res, src.nodata, src.count, src.dtypes)
    window = from_bounds(*aoi_bounds, transform=src.transform)
    dem = src.read(1, window=window, masked=True)      # masked array honors nodata
```

- Always check CRS, resolution, nodata value, band count and data type before computing. Treat nodata explicitly: a nodata of `-9999` averaged as a real value ruins statistics.
- **Resampling:** nearest neighbor for categorical rasters (land cover classes), bilinear or cubic for continuous values, average or mode when aggregating to coarser cells. Reproject with `gdalwarp` or rioxarray's `rio.reproject`, stating the method.
- **Scale and offset:** many satellite products store integers with a scale factor (for example surface reflectance) and quality or cloud-mask bands. Apply the documented scaling and masks before computing indices.
- Spectral indices are band arithmetic, for example NDVI = (NIR - Red) / (NIR + Red); confirm which band number is which for the specific sensor and product level (top-of-atmosphere versus surface reflectance), and guard against division by zero.
- **Zonal statistics** (raster values summarized per polygon) with `rasterstats` or `exactextract`; make sure polygons and raster share a CRS and decide how partially covered cells count.
- Large or many rasters: open lazily with rioxarray and Dask (`chunks=`), read COGs over HTTP by window, and search scenes through a STAC API by date, area and cloud cover instead of downloading archives.

## Data sources, licenses and terms

Check the license of every layer before combining or publishing:

- **OpenStreetMap** data is under the ODbL: attribute "© OpenStreetMap contributors", and share alike databases you derive and distribute. The public tile servers have a usage policy that forbids heavy or bulk use; use a tile provider or self-host for applications.
- **Natural Earth** small-scale boundaries and features are public domain.
- **Copernicus Sentinel** data is free and open with attribution; **Landsat** from the USGS is public domain.
- **Google Earth Engine** is free for research, education and noncommercial use; commercial use requires a paid license. Check the current terms for the user's case.
- Commercial imagery, geocoding and routing services restrict storage, caching and redistribution of results; read the terms before saving their output in a database.
- National statistical boundaries and census geographies change between vintages; join statistics only to the boundary vintage they were published for.

## Privacy

Precise locations are personal data: home and work locations identify people even without names. Aggregate to areas with enough people, round or jitter coordinates for display, suppress small counts, and do not publish raw traces. Note the duty under GDPR and similar laws (`../../legal-ready/GUIDE.md`).

## Maps

- Choropleths show rates or densities (per person, per km2), not raw counts, which mostly map population.
- State the classification scheme (quantiles, equal intervals, natural breaks) and show the legend with class bounds; choose a sequential palette for magnitudes and a diverging one around a meaningful midpoint.
- Use an equal-area projection for thematic world or continental maps, and include a scale bar and north arrow only where they add information.

## Checks (done when)

- [ ] CRS known and printed for every layer; measurements done in a suitable projected or geodesic method.
- [ ] A known point or feature lands where expected after each transformation.
- [ ] Join predicates chosen deliberately; unmatched and duplicated matches counted.
- [ ] Invalid geometries detected and repaired with a count; raster nodata, scale factors and masks applied.
- [ ] Licenses and attribution recorded for every source; personal location data aggregated before sharing.
- [ ] A visual check (QGIS or `explore()`) confirms the result looks right on a basemap.
