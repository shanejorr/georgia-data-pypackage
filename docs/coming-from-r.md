# Coming from R

The Python package mirrors the [R package](https://georgiacivicdata.org/r/):
the same functions, arguments, output columns and rules. The Python names
drop the `gcd_` prefix, because the import gives them one:
`import georgiacivicdata as gcd`, then `gcd.rows()`.

## The functions side by side

| R | Python |
|---|---|
| `gcd_datasets()` | {func}`gcd.datasets() <georgiacivicdata.datasets>` |
| `gcd_search()` | {func}`gcd.search() <georgiacivicdata.search>` |
| `gcd_describe()` | {func}`gcd.describe() <georgiacivicdata.describe>` |
| `gcd_columns()` | {func}`gcd.columns() <georgiacivicdata.columns>` |
| `gcd_contract()` | {func}`gcd.contract() <georgiacivicdata.contract>` |
| `gcd_rows()` | {func}`gcd.rows() <georgiacivicdata.rows>` |
| `gcd_values()` | {func}`gcd.values() <georgiacivicdata.values>` |
| `gcd_dimension()` | {func}`gcd.dimension() <georgiacivicdata.dimension>` |
| `gcd_school_zones()` | {func}`gcd.school_zones() <georgiacivicdata.school_zones>` |
| `gcd_district_boundaries()` | {func}`gcd.district_boundaries() <georgiacivicdata.district_boundaries>` |
| `gcd_school_zone_status()` | {func}`gcd.school_zone_status() <georgiacivicdata.school_zone_status>` |
| `gcd_school_zone_coverage()` | {func}`gcd.school_zone_coverage() <georgiacivicdata.school_zone_coverage>` |
| `gcd_locate()` | {func}`gcd.locate() <georgiacivicdata.locate>` |
| `gcd_meta()` | {func}`gcd.meta() <georgiacivicdata.meta>` |
| `gcd_citation()` | {func}`gcd.citation() <georgiacivicdata.citation>` |
| `gcd_cache_clear()` | {func}`gcd.cache_clear() <georgiacivicdata.cache_clear>` |
| `options(gcd.quiet = TRUE)` | `gcd.set_option("quiet", True)` |
| `options(gcd.cache = TRUE)` | `gcd.set_option("cache", True)` |

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
  Python raises {class}`~georgiacivicdata.GCDError` and its subclasses, with
  the same `code`, `status` and `details`.
- **Ids from `gcd.locate()`.** Without `id`, inputs are numbered from 0, the
  Python convention (R starts at 1).
