# georgiacivicdata.school_zone_status

### georgiacivicdata.school_zone_status(district_code=None, school_code=None, district=None, school=None, zone_status=None, no_zone_category=None, \*, backend=None)

Get each school's attendance-zone status.

Whether each school of the standard districts has an attendance zone on
the platform and, if not, why: a magnet or charter school with no zone, a
district whose maps are not published yet, and so on. Answers "why
doesn't this school have a zone?" without inferring it from a missing
polygon.

* **Parameters:**
  * **district_code** -- As in [`school_zones()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones).
  * **school_code** -- As in [`school_zones()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones).
  * **district** -- As in [`school_zones()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones).
  * **school** -- As in [`school_zones()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones).
  * **zone_status** (*str* *or* *list* *of* *str* *,* *optional*) -- `"zoned"`, `"no_zone"` and/or `"not_yet_collected"`. Default:
    all.
  * **no_zone_category** (*str* *or* *list* *of* *str* *,* *optional*) -- Why a school has no zone (the API's categories, listed by
    [`describe()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe) with `"school_attendance_zones"`). Default: all.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option.
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- One row per school, with columns `year` (integer),
  `district_code`, `district_name`, `school_code`,
  `school_name`, `zone_status`, `zone_levels` (the levels it is
  zoned for, as one string), `no_zone_category` and `reason`. The
  API's note on reading the table is `meta(x)["note"]`.

#### SEE ALSO
[`school_zones`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones)
: the zones.

[`school_zone_coverage`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zone_coverage.md#georgiacivicdata.school_zone_coverage)
: each district's coverage.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.school_zone_status(district="Atlanta Public Schools")
>>> gcd.school_zone_status(zone_status="no_zone")
```
