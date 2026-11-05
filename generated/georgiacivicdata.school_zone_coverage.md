# georgiacivicdata.school_zone_coverage

### georgiacivicdata.school_zone_coverage(district_code=None, district=None, \*, geometry=False, backend=None)

Get each district's attendance-zone coverage.

How completely each standard district's attendance zones were collected,
one row per district and zone level: the source tier, the status of each
level, the share of the district's land and 2020 population the zones
cover, how they were built, and the reason for anything short of
complete.

The API returns one row per district with a column per level
(`level_status_elementary`, `pct_population_middle`, ...); this
function pivots those columns long. The district filter runs locally
(the route takes no filters; the table has about 180 rows).

* **Parameters:**
  * **district_code** -- As in [`district_boundaries()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.district_boundaries.md#georgiacivicdata.district_boundaries).
  * **district** -- As in [`district_boundaries()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.district_boundaries.md#georgiacivicdata.district_boundaries).
  * **geometry** (*bool* *,* *default False*) -- `False` returns a data frame; `True` returns a `GeoDataFrame`
    of the district outlines carrying the same fields.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- With `geometry=False`, the kind of data frame to return.
* **Returns:**
  *DataFrame or geopandas.GeoDataFrame* -- One row per district and zone level, with columns `year`
  (integer), `district_code`, `district_name`, `tier` (the source
  tier, A to E or N), `status` (the district's overall status),
  `zone_level`, `level_status` (`"zoned"`,
  `"one_school_per_grade"`, `"partial"`, `"not_available"`,
  `"served_by_other_district"`), `pct_land_area` and
  `pct_population` (0-1, the share the level's zones cover),
  `zone_count`, `methods`, `accuracy_classes`, `reason`, then
  `levels_covered`, `currency_statuses`, `best_lead`,
  `extension_note` and `served_elsewhere` (a list column of dicts:
  the other district's school serving that level, with
  `district_code`, `school_code` and `reason`).

#### SEE ALSO
[`school_zones`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones)
: the zones.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.school_zone_coverage(district="Clay County")
>>> coverage = gcd.school_zone_coverage()
>>> coverage.groupby(["zone_level", "level_status"]).size()
```
