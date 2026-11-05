# Coming from R

The Python package mirrors the [R package](https://georgiacivicdata.org/r/):
the same functions, arguments, output columns and rules. The Python names
drop the `gcd_` prefix, because the import gives them one:
`import georgiacivicdata as gcd`, then `gcd.rows()`.

## The functions side by side

| R                            | Python                                                                                                                                                   |
|------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `gcd_datasets()`             | [`gcd.datasets()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets)                                     |
| `gcd_search()`               | [`gcd.search()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.search.md#georgiacivicdata.search)                                           |
| `gcd_describe()`             | [`gcd.describe()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)                                     |
| `gcd_columns()`              | [`gcd.columns()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns)                                        |
| `gcd_contract()`             | [`gcd.contract()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.contract.md#georgiacivicdata.contract)                                     |
| `gcd_rows()`                 | [`gcd.rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows)                                                 |
| `gcd_values()`               | [`gcd.values()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.values.md#georgiacivicdata.values)                                           |
| `gcd_dimension()`            | [`gcd.dimension()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.dimension.md#georgiacivicdata.dimension)                                  |
| `gcd_school_zones()`         | [`gcd.school_zones()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones)                         |
| `gcd_district_boundaries()`  | [`gcd.district_boundaries()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.district_boundaries.md#georgiacivicdata.district_boundaries)    |
| `gcd_school_zone_status()`   | [`gcd.school_zone_status()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zone_status.md#georgiacivicdata.school_zone_status)       |
| `gcd_school_zone_coverage()` | [`gcd.school_zone_coverage()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zone_coverage.md#georgiacivicdata.school_zone_coverage) |
| `gcd_locate()`               | [`gcd.locate()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.locate.md#georgiacivicdata.locate)                                           |
| `gcd_meta()`                 | [`gcd.meta()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.meta.md#georgiacivicdata.meta)                                                 |
| `gcd_citation()`             | [`gcd.citation()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.citation.md#georgiacivicdata.citation)                                     |
| `gcd_cache_clear()`          | [`gcd.cache_clear()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.cache_clear.md#georgiacivicdata.cache_clear)                            |
| `options(gcd.quiet = TRUE)`  | `gcd.set_option("quiet", True)`                                                                                                                          |
| `options(gcd.cache = TRUE)`  | `gcd.set_option("cache", True)`                                                                                                                          |

## The same call in both

```r
gcd_rows(
  "graduation_rate_4_year_cohort",
  district = "Fulton County",
  demographic = c("all", "black"),
  year = 2020:2024
)
```

```python
gcd.rows(
    "graduation_rate_4_year_cohort",
    district="Fulton County",
    demographic=["all", "black"],
    year=range(2020, 2025),
)
```

## What differs, and why

- **Data frames.** R returns tibbles; Python returns pandas data frames by
  default, or Polars with `backend="polars"` (per call) or
  `gcd.set_option("backend", "polars")` (per session). pandas results use
  nullable dtypes (`Int64`, `boolean`, `string`), so missing values stay
  missing and codes stay text; floats are `float64` with `NaN`.
- **Geometry.** R returns `sf` objects; Python returns geopandas
  `GeoDataFrame`s, in WGS 84. `geometry=False` gives a plain table in
  either.
- **Years.** `range(2020, 2025)` is 2020 to 2024: Python ranges leave out
  their end. A list such as `[2015, 2025]` asks for exact years, as `c()`
  does in R.
- **Missing values in filters.** A filter set to `None` is ignored, like
  R's `NULL`. `None` *inside a list* (`assessment_type=[None]`) selects rows
  where the column is empty, like `NA` in R.
- **All rows.** `n_max=None` (the default) returns every row, like `Inf` in
  R.
- **Integers.** Every integer column is 64-bit; R switches to doubles past
  its 32-bit limit.
- **Messages.** The API's advisories are `GCDAdvisory` warnings, the Python
  way to say "this result needs care"; progress notes go to standard error.
  `quiet=True` silences both, as in R.
- **Metadata.** R keeps metadata in attributes. Polars data frames have no
  attributes, so `gcd.meta(df)` reads it from a registry kept beside each
  result (pandas results also carry it in `df.attrs`). Read it from the
  result as it came back: a new data frame derived from it doesn't carry
  it. `gcd.meta()` also returns the notes of `gcd.search()`
  (`confidence`), the zone functions and `gcd.locate()` (`note`,
  `assignment_note`), which R keeps as attributes.
- **Errors.** R raises classed conditions (`gcd_error_topic_not_found`);
  Python raises [`GCDError`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDError.md#georgiacivicdata.GCDError) and its subclasses, with
  the same `code`, `status` and `details`.
- **Ids from `gcd.locate()`.** Without `id`, inputs are numbered from 0, the
  Python convention (R starts at 1).
