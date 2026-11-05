# georgiacivicdata.district_boundaries

### georgiacivicdata.district_boundaries(district_code=None, district=None, \*, geometry=True, backend=None)

Get school district boundaries.

The Census TIGER/Line outlines of Georgia's school districts, keyed to
district codes: unified districts, the secondary-only pieces some
districts serve (Fort Benning grades 9-12), and the Department of
Defense districts (which have no district code).

* **Parameters:**
  * **district_code** (*str* *or* *list* *of* *str* *,* *optional*) -- District codes. Default: every district.
  * **district** (*str* *or* *list* *of* *str* *,* *optional*) -- District names, matched to codes as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows).
  * **geometry** (*bool* *,* *default True*) -- `True` returns a geopandas `GeoDataFrame`; `False` returns the
    attributes as a plain data frame.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- With `geometry=False`, the kind of data frame to return.
* **Returns:**
  *geopandas.GeoDataFrame or DataFrame* -- One row per district piece, with columns `district_code`,
  `district_name` (for Department of Defense districts, the Census
  name), `boundary_type` (`"unified"`, `"secondary_extension"` or
  `"dodea"`), `district_census_id`, `nces_lea_id`, `grade_low`,
  `grade_high`, `tiger_geoid`, `tiger_name`, `tiger_vintage`,
  `land_area_sq_mi`, `area_sq_mi`, the bounding box and the
  `geometry` (WGS 84).

#### SEE ALSO
[`school_zones`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones)
: the zones inside each district.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.district_boundaries(district="Clay County")
>>> gcd.district_boundaries(geometry=False)
```
