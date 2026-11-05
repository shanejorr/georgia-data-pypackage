# georgiacivicdata.locate

### georgiacivicdata.locate(lat=None, lon=None, address=None, id=None, grade=None, year=None, \*, quiet=False, backend=None)

Locate points or addresses.

The county, 2020 Census tract and block group, school district and zoned
schools that points or street addresses fall in.

Points are sent to the API's `POST /locate` route in batches of up to
1,000, so coordinates never appear in URLs and nothing is cached.
**Addresses never reach the Georgia Civic Data API**: the package
geocodes them on your computer with the U.S. Census batch geocoder
([https://geocoding.geo.census.gov/geocoder/](https://geocoding.geo.census.gov/geocoder/), benchmark
`Public_AR_Current`, the address data the API's own search uses; up to
10,000 addresses per upload), then sends the coordinates as points. An
address the Census can't match is never sent. To geocode with another
service, geocode first and pass `lat` and `lon`.

A zone is the default assignment, not the only option: a student may
attend another public school by transfer, or a charter, magnet or other
choice school. This is not an official enrollment determination; confirm
with the school district.

**Output.** A long data frame: **for each input, one row per place it
falls in.** A typical location gives seven rows: its county, tract, block
group and school district, then one row per zoned school. Rows for each
input come in a fixed order: county, tract, block group, district, then
elementary, middle and high schools by grade.

A level can have more than one school row: some homes are zoned to one
elementary school for kindergarten to grade 2 and another for grades
3-5. The `grades` column tells them apart; pass `grade` to keep only
the school for one grade.

The `note` column is missing normally, and one plain sentence
otherwise, so a missing row is never silent:

- a level with no zone collected yet, a gap between zones, or a level
  served by another district gets a row with missing id, name and
  grades, and a note saying why;
- an input outside Georgia, a point the API rejects, or an address the
  Census can't match gets one row with missing geographic columns and
  the reason; one bad input never stops the batch;
- in a Department of Defense district the district row has a missing id
  and a note;
- school rows whose zone has a known pending change, or which overlap
  another school's zone, say so.

* **Parameters:**
  * **lat** (*float* *or* *sequence* *of* *float* *,* *optional*) -- Latitude and longitude in decimal degrees (WGS 84), of equal length.
  * **lon** (*float* *or* *sequence* *of* *float* *,* *optional*) -- Latitude and longitude in decimal degrees (WGS 84), of equal length.
  * **address** (*str* *,* *sequence* *of* *str* *, or* *DataFrame* *,* *optional*) -- Street addresses: one-line addresses
    (`"206 Washington St SW, Atlanta, GA 30334"`), or a data frame
    (pandas or Polars) or dict with columns `street`, `city`,
    `state` and `zip`. Give either `lat` and `lon` or
    `address`, not both.
  * **id** (*sequence* *,* *optional*) -- Identifiers for the inputs, the same length, carried into the output
    so results join back to your data. Default: each input's position,
    starting at 0.
  * **grade** (*str* *or* *int* *,* *optional*) -- Keep only school zones serving this grade (`"pk"`, `"k"`,
    `"01"` to `"12"`; `"5"`, `5` and `"K"` are accepted).
    Default: every grade.
  * **year** (*int* *,* *optional*) -- The zones' school year as its ending year (2027 is 2026-27).
    Default: the current zones.
  * **quiet** (*bool* *,* *default False*) -- `True` silences the once-per-session note on the default
    assignment.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option.
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- Columns, in order:
  1. `id`.
  2. The input: `lat`, `lon` for points; for addresses
     `address`, the geocoder's `match_status` (`"match"`,
     `"no_match"`, `"tie"`), `match_type` (`"exact"`,
     `"non_exact"`), `matched_address`, and the geocoded `lat`
     and `lon`.
  3. `geographic_type`: `"county"`, `"tract"`, `"block_group"`,
     `"school_district"`, `"elementary_school"`,
     `"middle_school"` or `"high_school"`.
  4. `geographic_id`: county FIPS (`"13121"`), tract GEOID
     (`"13121003500"`), block group GEOID (`"131210035001"`),
     district code (`"761"`), or for a school `"DISTRICT-SCHOOL"`
     (`"761-4560"`), the form [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) takes as `school_id`.
  5. `geographic_name`: the place's name.
  6. `grades`: a school row's grade range (`"K-5"`, `"6-8"`,
     `"9-12"`); missing on other rows.
  7. `note`: missing, or why a row is missing or needs care.

  [`meta()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.meta.md#georgiacivicdata.meta) on the result gives the API's `assignment_note` and
  `note` on reading the zones.

#### SEE ALSO
[`school_zones`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones)
: the zones' shapes and precision (`method`, `accuracy_class`).

[`rows`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows)
: with `school_id`, data on a located school.

### Examples

```pycon
>>> import georgiacivicdata as gcd
```

The Georgia State Capitol, by coordinates and by address:

```pycon
>>> gcd.locate(lat=33.7490, lon=-84.3880)
>>> gcd.locate(address="206 Washington St SW, Atlanta, GA 30334")
```

Only the school for one grade:

```pycon
>>> gcd.locate(lat=33.7490, lon=-84.3880, grade=9)
```
