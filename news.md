# Changelog

## georgiacivicdata 0.1.0 (unreleased)

First version: the Python counterpart of the R package georgiacivicdata.

### Features

- Find data: `datasets()` lists the catalog and `search()` ranks datasets
  from plain words, in English or Spanish.
- Understand a dataset: `describe()` (with a readable printed summary),
  `columns()` and `contract()`. `columns()` lists the joined name columns
  `rows()` returns by default (`labels=True`), each after its code with
  `role` `"label"`.
- Get data: `rows()` returns typed data frames with place names beside
  codes, every category the filters don't exclude, the API's advisories as
  `GCDAdvisory` warnings, and metadata read by `meta()`; large results
  download in full as CSV. `values()` lists the category combinations a
  filter covers.
- pandas or Polars: every table function takes `backend=`, and
  `set_option("backend", "polars")` changes the default for the session.
- Lookup tables: `dimension()` returns districts, schools, counties,
  tracts, block groups and demographic groups.
- Places by name: `district`, `school` and `county` arguments match names
  exactly (ignoring case, accents and a trailing "County", and including
  former names) and stop with candidates when a name is ambiguous.
- Geography: `school_zones()`, `district_boundaries()`,
  `school_zone_status()` and `school_zone_coverage()`, as geopandas
  `GeoDataFrame`s or plain data frames.
- `locate()` finds the county, tract, block group, school district and
  zoned schools for points, or for addresses geocoded locally with the U.S.
  Census batch geocoder (addresses never reach the Georgia Civic Data API).
- Utilities: `meta()`, `citation()`, `cache_clear()` and the options
  functions, with an opt-in disk cache of row downloads that revalidates
  with the server's `ETag`.
