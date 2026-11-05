# georgiacivicdata.dimension

### georgiacivicdata.dimension(name, \*, district=None, school=None, county=None, q=None, columns=None, n_max=None, backend=None, \*\*filters)

Get the rows of a lookup table.

Returns one of the platform's six lookup tables, the reference lists
every dataset's codes point to. They hold much more than names, and the
API never adds it to dataset rows:

- `"districts"`: district name, former names, type, Census id, county,
  address, coordinates, active flag.
- `"schools"`: school name, former names, level, grade span, county,
  NCES id, address, phone, website, coordinates, locale (city, suburb,
  town, rural), charter and active flags.
- `"counties"`: the 159 county names (without "County").
- `"tracts"`: 2020 Census tracts with county, land area and population.
- `"block_groups"`: 2020 block groups with tract, county, land area,
  population, housing units and households.
- `"demographics"`: each demographic group's label and category.

Use it to analyze results by locale, map schools, or browse what exists
("every school in Fulton County"). Unfiltered tables are cached for the
session.

**Joining schools.** School codes repeat across districts, so join on
`district_code` **and** `school_code` together:

```default
schools = gcd.dimension(
    "schools", columns=["district_code", "school_code", "locale"]
)
grad.merge(schools, on=["district_code", "school_code"], how="left")
```

* **Parameters:**
  * **name** (*str*) -- The lookup table: `"districts"`, `"schools"`, `"counties"`,
    `"tracts"`, `"block_groups"` or `"demographics"`.
  * **district** (*str* *or* *list* *of* *str* *,* *optional*) -- Places by name, matched exactly against current and former names
    (ignoring case, accents and a trailing "County") and turned into
    codes. Each applies only to tables with that code column.
  * **school** (*str* *or* *list* *of* *str* *,* *optional*) -- Places by name, matched exactly against current and former names
    (ignoring case, accents and a trailing "County") and turned into
    codes. Each applies only to tables with that code column.
  * **county** (*str* *or* *list* *of* *str* *,* *optional*) -- Places by name, matched exactly against current and former names
    (ignoring case, accents and a trailing "County") and turned into
    codes. Each applies only to tables with that code column.
  * **q** (*str* *,* *optional*) -- Partial text search over the table's name columns, ignoring case and
    accents (`q="eastside"`). Unlike the name arguments, it matches
    part of a name and returns every hit, so it is the tool for browsing.
  * **columns** (*str* *or* *list* *of* *str* *,* *optional*) -- The columns to return. Default: all.
  * **n_max** (*int* *,* *optional*) -- The most rows to return. Default `None`: all.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option
    (`"pandas"` unless changed with [`set_option()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.set_option.md#georgiacivicdata.set_option)).
  * **\*\*filters** -- Named filters on the table's key, enum and boolean columns, and
    `county_fips`, `district_code` or `tract_geoid` where the table
    has them. Each takes a value or a list (values are OR'd; filters are
    AND'd), for example `active=True`,
    `district_type="state_charter"` or `county_fips="13121"`.
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- One row per district, school, county, tract, block group or
  demographic group, ordered by the table's primary key and typed from
  its schema: codes (`district_code`, `school_code`,
  `county_fips`, `tract_geoid`, `block_group_geoid`,
  `demographic`) and text columns are strings, coordinates and areas
  floats, counts and `directory_year` integers, `active` and
  `charter` booleans. See [`columns()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns) for each table's columns.

#### SEE ALSO
[`columns`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns)
: a table's column dictionary.

[`rows`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows)
: results carry these tables' names beside their codes.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.dimension("counties")
>>> gcd.dimension("schools", county="Fulton", active=True)
>>> gcd.dimension("districts", district_type="state_charter")
>>> gcd.dimension(
...     "schools", q="eastside",
...     columns=["district_code", "school_code", "school_name"],
... )
```
