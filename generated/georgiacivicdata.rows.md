# georgiacivicdata.rows

### georgiacivicdata.rows(name, \*, year=None, detail=None, district=None, school=None, county=None, labels=True, columns=None, sort=None, n_max=None, cache=None, quiet=False, backend=None, \*\*filters)

Get rows of a dataset.

The core function: the rows of one dataset at one detail level, as a
data frame typed from the dataset's schema, with place names beside
their codes.

**It returns every category and group the filters don't exclude.**
Nothing is pinned by default: no single demographic group, no single
subject. A call with only a dataset name returns the whole dataset at its
default detail level.

**Filters.** Give filters as keyword arguments; each value is one value
or a list. Values within one filter are OR'd; different filters are
AND'd. Accepted names:

- any categorical column: `subject="mathematics"`,
  `demographic=["all", "black"]`;
- geography codes: `district_code`, `school_code`, `county_fips`,
  `tract_geoid`, `block_group_geoid`;
- `school_id`: schools as `"DISTRICT-SCHOOL"` codes
  (`school_id=["761-0199", "660-0104"]`), the form [`locate()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.locate.md#georgiacivicdata.locate)
  returns (a school code alone is not unique across districts);
- lookup-table attributes: `district_type="state_charter"`,
  `school_level="high"`, `locale="rural"`,
  `demographic_category="race"`;
- metric bounds: `graduation_rate_min=0.9`, `num_cohort_max=50`
  (inclusive, in stored units).

`None` inside a list selects rows where a nullable column is empty
(`assessment_type=[None]`); a filter that is `None` itself is
ignored. Booleans become `true` / `false`. The API validates every
filter and its errors name what went wrong; [`describe()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe) lists each
dataset's filters and their values.

**Labels.** With `labels=True` (the default) the rows carry the API's
joined name columns, each right after its code: `district_name`,
`district_census_id` and `district_type` after `district_code`;
`school_name` after `school_code`; `county_name`, `tract_name`
and `block_group_name` after their codes; `demographic_label` and
`demographic_category` after `demographic`. Codes are always kept:
school names repeat across districts, names change over time, and joins
run on codes. Categorical values (`subject`, `grade_cluster`) are
readable snake_case codes already. Other lookup-table attributes (school
addresses, locale, coordinates) are not joined; get them from
[`dimension()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.dimension.md#georgiacivicdata.dimension) and merge. `labels=False` asks for the dataset's own
columns only, for large pulls. Either way, code columns that would be
empty on every row (a district row's `school_code`, a state row's
geography codes) are left out, so both settings give the same shape.

**Missing values and totals.** A missing metric usually means the value
was **suppressed** to protect privacy (small counts), **not zero**; the
schema's `null_semantics` says which ([`describe()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)). Because
nothing is pinned, results hold the `all` totals beside the subgroups:
never add a total to its subgroups. The API's advisories say so when
they apply, as [`GCDAdvisory`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDAdvisory.md#georgiacivicdata.GCDAdvisory) warnings (`quiet=True` or
`set_option("quiet", True)` silences them; they stay in
`meta(df)["advisories"]`). Rates must be pooled from their counts,
never averaged: `sum(num_graduates) / sum(num_cohort)`, not
`mean(graduation_rate)`. [`columns()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns) shows each metric's
numerator and denominator.

**Large downloads and the disk cache.** Up to 10,000 rows come back as
one JSON page. A larger result is downloaded in full as CSV in one
response; the metadata and advisories then come from the first JSON page
and describe its first 10,000 rows. With `cache=True` (or
`set_option("cache", True)`), responses are kept in the user cache
folder with their `ETag`. Repeating a request asks the server whether
the data changed: an unchanged answer reuses the saved copy without
downloading, and a new data release downloads afresh. A response the
server marks fresh (for five minutes) is reused without asking. Clear it
with [`cache_clear()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.cache_clear.md#georgiacivicdata.cache_clear).

**Data license.** The data is CC BY 4.0: credit Georgia Civic Data and
the original source, as [`citation()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.citation.md#georgiacivicdata.citation) writes.

* **Parameters:**
  * **name** (*str*) -- The dataset's name, such as `"graduation_rate_4_year_cohort"` (see
    [`datasets()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets) and [`search()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.search.md#georgiacivicdata.search)).
  * **year** (*int* *or* *list* *of* *int* *,* *optional*) -- Years to keep. A run of consecutive years (`range(2019, 2025)`) is
    sent as a range; anything else (`[2019, 2024]`) as exact years.
    Default: all years.
  * **detail** (*str* *,* *optional*) -- The one level the rows describe, such as `"schools"`,
    `"districts"`, `"states"`, `"counties"` or `"tracts"`.
    Default: the dataset's default (the finest level, except Census
    datasets, which default to counties). To combine levels, call once
    per level and concatenate.
  * **district** (*str* *or* *list* *of* *str* *,* *optional*) -- Places by name, such as `district="Fulton County"`,
    `school="Roswell High School"`, `county=["Fulton", "DeKalb"]`.
    Matched exactly against current and former names (ignoring case,
    accents and a trailing "County"); an unknown or ambiguous name is an
    error that lists suggestions or candidates. A school name found in
    more than one district needs `district` too. For any one place,
    give its code or its name, not both.
  * **school** (*str* *or* *list* *of* *str* *,* *optional*) -- Places by name, such as `district="Fulton County"`,
    `school="Roswell High School"`, `county=["Fulton", "DeKalb"]`.
    Matched exactly against current and former names (ignoring case,
    accents and a trailing "County"); an unknown or ambiguous name is an
    error that lists suggestions or candidates. A school name found in
    more than one district needs `district` too. For any one place,
    give its code or its name, not both.
  * **county** (*str* *or* *list* *of* *str* *,* *optional*) -- Places by name, such as `district="Fulton County"`,
    `school="Roswell High School"`, `county=["Fulton", "DeKalb"]`.
    Matched exactly against current and former names (ignoring case,
    accents and a trailing "County"); an unknown or ambiguous name is an
    error that lists suggestions or candidates. A school name found in
    more than one district needs `district` too. For any one place,
    give its code or its name, not both.
  * **labels** (*bool* *,* *default True*) -- `True` adds place names beside codes; `False` returns codes only.
  * **columns** (*str* *or* *list* *of* *str* *,* *optional*) -- Return only these columns. Default: all.
  * **sort** (*str* *or* *list* *of* *str* *,* *optional*) -- Columns to sort by on the server; prefix `-` for descending
    (`"-graduation_rate"`). Missing values sort last. Mostly useful
    with `n_max` for a top N. Default: the dataset's own order (its
    grain).
  * **n_max** (*int* *,* *optional*) -- The most rows to return. Default `None`: all.
  * **cache** (*bool* *,* *optional*) -- `True` to use the disk cache. Default: the `cache` option
    (`False`).
  * **quiet** (*bool* *,* *default False*) -- `True` silences the advisories.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option
    (`"pandas"`).
  * **\*\*filters** -- Named filters (see "Filters" above).
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- Rows at one detail level, typed from the schema: codes and names are
  strings (leading zeros kept), `year` and counts integers, rates and
  proportions floats (proportions on the 0-1 scale), booleans boolean.
  In pandas, integers are `Int64`, booleans `boolean` and text
  `string` (nullable dtypes); floats are `float64`. Columns come in
  grain order: `year`, each geography code followed by its names,
  `demographic` and its labels, other categorical columns, then
  metrics. [`columns()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns) describes each column. [`meta()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.meta.md#georgiacivicdata.meta) returns
  the response's metadata: dataset, title, detail, key metric, units,
  `null_semantics`, source, citation, license, advisories, data
  version, `updated_at` and the request URL.

#### SEE ALSO
[`values`](https://georgiacivicdata.org/py/generated/georgiacivicdata.values.md#georgiacivicdata.values)
: which category values exist under a filter.

[`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe), [`columns`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns)

[`citation`](https://georgiacivicdata.org/py/generated/georgiacivicdata.citation.md#georgiacivicdata.citation)
: cite it.

### Examples

```pycon
>>> import georgiacivicdata as gcd
```

Names and codes (the default), one district by name:

```pycon
>>> grad = gcd.rows(
...     "graduation_rate_4_year_cohort",
...     district="Fulton County",
...     demographic=["all", "black", "hispanic"],
...     year=range(2020, 2025),
... )
```

One school, by name within its district:

```pycon
>>> gcd.rows(
...     "graduation_rate_4_year_cohort",
...     district="Fulton County", school="Roswell High School",
...     demographic="all",
... )
```

Statewide schools, one subject, codes only, as Polars:

```pycon
>>> gcd.rows(
...     "ccrpi_content_mastery", year=2025, detail="schools",
...     grade_cluster="high", subject="mathematics", labels=False,
...     backend="polars",
... )
```

Top 10 counties by unemployment:

```pycon
>>> gcd.rows("employment", year=2024, sort="-unemployment_rate", n_max=10)
```
