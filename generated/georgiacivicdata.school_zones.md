# georgiacivicdata.school_zones

### georgiacivicdata.school_zones(district_code=None, school_code=None, district=None, school=None, zone_level=None, grade=None, year=None, resolution='display', \*, geometry=True, backend=None)

Get school attendance zones.

Attendance-zone polygons: the areas that assign a home to its zoned
elementary, middle and high school, one polygon per school, level and
grade run, for the current school year.

**Zones differ in precision.** Some are the district's official GIS
layers; others are digitized from PDF maps, rebuilt from street lists,
or are the whole district outline (districts with one school per grade).
Read `method` and `accuracy_class` before treating zones as equally
exact, and see [`school_zone_coverage()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zone_coverage.md#georgiacivicdata.school_zone_coverage) for how completely each
district was collected. A zone is the default assignment, not an
official enrollment determination: confirm with the district.

**A statewide pull is large**, especially at `resolution="full"`.
Filter to a district and keep the `"display"` default for maps.

* **Parameters:**
  * **district_code** (*str* *or* *list* *of* *str* *,* *optional*) -- Codes.
  * **school_code** (*str* *or* *list* *of* *str* *,* *optional*) -- Codes.
  * **district** (*str* *or* *list* *of* *str* *,* *optional*) -- Names, matched to codes as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows). A school name found in
    more than one district needs `district` too.
  * **school** (*str* *or* *list* *of* *str* *,* *optional*) -- Names, matched to codes as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows). A school name found in
    more than one district needs `district` too.
  * **zone_level** (*str* *or* *list* *of* *str* *,* *optional*) -- `"elementary"`, `"middle"` and/or `"high"`. Default: all.
  * **grade** (*str* *or* *int* *,* *optional*) -- One grade: keep zones serving it (`"pk"`, `"k"`, `"01"` to
    `"12"`; `"5"`, `5` and `"K"` are accepted). Default: all.
  * **year** (*int* *,* *optional*) -- The zones' school year as its ending year (2027 is 2026-27).
    Default: the current zones.
  * **resolution** ( *{"display"* *,*  *"full"}* *,* *default "display"*) -- `"display"`: simplified polygons for maps, much smaller;
    `"full"`: the source polygons the point lookup uses.
  * **geometry** (*bool* *,* *default True*) -- `True` returns a geopandas `GeoDataFrame` (needs the `geo`
    extra: `pip install georgiacivicdata[geo]`); `False` returns the
    attributes as a plain data frame.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- With `geometry=False`, the kind of data frame to return (default:
    the `backend` option). Geometry is always a `GeoDataFrame`.
* **Returns:**
  *geopandas.GeoDataFrame or DataFrame* -- One row per zone, with columns `year` (integer), `district_code`,
  `district_name`, `school_code`, `school_name`, `zone_level`,
  `grade_low`, `grade_high` (`"pk"`, `"k"`, `"01"` ...
  `"12"`), `method` (how the zone was built), `accuracy_class`,
  `currency_status`, `boundary_vintage`, `source_url`,
  `retrieved_on` (date), `area_sq_mi`, the bounding box
  (`bbox_xmin`, `bbox_ymin`, `bbox_xmax`, `bbox_ymax`),
  `source_school_name` (the name as the district's map spells it),
  then `positional_rmse_m`, `currency_note`, `source_publisher`,
  `nces_school_id`, `district_census_id`, `nces_lea_id` and the
  `geometry` (WGS 84). The API's disclaimer is `meta(x)["note"]`.

#### SEE ALSO
[`locate`](https://georgiacivicdata.org/py/generated/georgiacivicdata.locate.md#georgiacivicdata.locate)
: the zones a point falls in.

[`school_zone_status`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zone_status.md#georgiacivicdata.school_zone_status)
: schools without a zone.

[`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)
: with `"school_attendance_zones"`, every field.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> zones = gcd.school_zones(
...     district="Atlanta Public Schools", zone_level="high"
... )
>>> zones.plot(column="school_name")
>>> gcd.school_zones(district_code="630", geometry=False)
```
