---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Get started

`georgiacivicdata` reads the [Georgia Civic Data](https://georgiacivicdata.org)
API: cleaned public data about Georgia's schools and communities. The
[home page](../index.ipynb) walks through the basic workflow (search for a
dataset, read its columns, get its rows, plot them and cite them) with
Fulton County's graduation rate. This article covers what that example
leaves out: how to narrow the catalog, how names and filters work, and the
rules of the data that are easy to get wrong.

```{code-cell} ipython3
:tags: [remove-cell]

import warnings

import pandas as pd

warnings.formatwarning = lambda message, category, *args, **kwargs: (
    f"{category.__name__}: {message}\n"
)
pd.set_option("display.width", 100)
pd.set_option("display.max_columns", 10)
pd.set_option("display.max_colwidth", 45)
```

```{code-cell} ipython3
import georgiacivicdata as gcd
```

## Browse the catalog

`gcd.datasets()` is the whole catalog, one row per dataset. Every argument
narrows it on the server:

```{code-cell} ipython3
catalog = gcd.datasets()
catalog.groupby(["main_topic", "kind"]).size()
```

```{code-cell} ipython3
gcd.datasets(main_topic="education", level="districts", year=2025)[["name", "title"]].head()
```

## Read a dataset's notes

`gcd.describe()` prints what a dataset holds, where it comes from, its years
and detail levels, the columns that identify a row (its *grain*) and the
notes its data contract declares:

```{code-cell} ipython3
gcd.describe("graduation_rate_4_year_cohort")
```

Some categorical columns have no total. `gcd.describe()` lists them under
**"Pick one value of"**: for example, `grade_cluster` and `subject` in
`ccrpi_content_mastery`, whose values must not be mixed in one summary. The
result's `filters` table shows every filter:

```{code-cell} ipython3
d = gcd.describe("ccrpi_content_mastery")
d.filters.loc[d.filters["kind"] == "categorical", ["param", "has_total", "requires_single_value"]]
```

## Filter by name or by code

Name a district, school or county and the package turns it into a code.
Names match exactly, ignoring case, accents and a trailing "County", and
former names work too:

```{code-cell} ipython3
gcd.rows(
    "graduation_rate_4_year_cohort",
    district="Fulton County",
    school="Riverwood High School",  # a former name
    demographic="all",
    year=range(2021, 2026),
    quiet=True,
)[["year", "district_code", "school_code", "school_name", "graduation_rate"]]
```

A name that matches more than one place stops with the candidates instead
of guessing. "Eastside Elementary School" is in several districts, and
Fulton County has an old and a new "Milton High School". The error is a
`GCDPlaceAmbiguousError`, so a script can catch it:

```{code-cell} ipython3
try:
    gcd.rows("graduation_rate_4_year_cohort", school="Milton High School", district="Fulton County")
except gcd.GCDPlaceAmbiguousError as err:
    print(err)
```

Codes work everywhere names do. A school is identified by its district and
school codes together, written `"DISTRICT-SCHOOL"` in `school_id`:

```{code-cell} ipython3
gcd.rows(
    "graduation_rate_4_year_cohort",
    school_id="660-0106",
    demographic="all",
    year=2025,
    quiet=True,
)[["year", "school_code", "school_name", "num_graduates", "num_cohort", "graduation_rate"]]
```

## Years and detail levels

`year=range(2021, 2026)` asks for 2021 to 2025 (a Python range leaves out its
end); `year=[2015, 2025]` asks for those two years only. Each call returns
one **detail level**: schools, districts, states, counties or tracts,
whatever the dataset publishes. The default is the finest level (counties
for Census datasets). Columns that would be empty at a level are left out:

```{code-cell} ipython3
gcd.rows(
    "graduation_rate_4_year_cohort",
    detail="states",
    demographic="all",
    year=[2015, 2025],
    quiet=True,
)
```

To combine levels, call once per level and concatenate the rows
(`pd.concat`).

## What a missing value means

A missing metric usually means the value was **suppressed** to protect
privacy (small counts), **not zero**. The schema's `null_semantics` says
which, and `gcd.rows()` passes on the API's advisory when a result holds
suppressed values:

```{code-cell} ipython3
small = gcd.rows(
    "graduation_rate_4_year_cohort",
    district="Appling County",
    year=2024,
    detail="districts",
)
small[["demographic", "num_graduates", "num_cohort", "graduation_rate"]].head()
```

The advisories are `GCDAdvisory` warnings. They stay with the result in
`gcd.meta(small)["advisories"]`; `quiet=True` (or
`gcd.set_option("quiet", True)`) silences them, and the usual
[`warnings`](https://docs.python.org/3/library/warnings.html) filters work too:

```{code-cell} ipython3
[a["code"] for a in gcd.meta(small)["advisories"]]
```

## Totals beside subgroups

Nothing is pinned by default, so a result holds the `all` total beside every
subgroup, and subgroups from different categories overlap (a student is in a
race group, a gender group and an economic group at once). Never add them
up:

```{code-cell} ipython3
fulton = gcd.rows(
    "graduation_rate_4_year_cohort",
    district="Fulton County",
    detail="districts",
    year=2025,
    quiet=True,
)
pd.Series(
    {
        "published_total": fulton.loc[fulton["demographic"] == "all", "num_cohort"].iloc[0],
        "sum_of_every_row": fulton["num_cohort"].sum(),
    }
)
```

Use the published `all` row for totals, and filter one category
(`demographic_category="race"`) to compare groups.

## Which values exist: `gcd.values()`

When a filter returns nothing, `gcd.values()` shows which combinations exist
under the other filters, with row counts, without downloading rows:

```{code-cell} ipython3
combos = gcd.values(
    "ccrpi_content_mastery", ["grade_cluster", "subject"], year=2025, detail="districts"
)
combos.head()
```

## Lookup tables

There are six lookup tables: `districts`, `schools`, `counties`, `tracts`,
`block_groups` and `demographics`. `gcd.dimension()` returns any of them.
**School codes repeat across districts**, so join schools on
`district_code` and `school_code` together, never `school_code` alone:

```{code-cell} ipython3
schools = gcd.dimension("schools", columns=["district_code", "school_code"])
schools["school_code"].value_counts().head(3)
```

## pandas or Polars

pandas is the default. Pass `backend="polars"` to any table function, or set
it for the session:

```{code-cell} ipython3
gcd.set_option("backend", "polars")
gcd.dimension("counties", n_max=3)
```

```{code-cell} ipython3
gcd.set_option("backend", "pandas")
```

pandas results use nullable dtypes: integers are `Int64`, booleans
`boolean` and text `string`, so a missing value is `<NA>` and codes keep
their leading zeros; floats stay `float64`, with `NaN` for missing. Polars
results get the same types natively. Geometry always comes back as a
geopandas `GeoDataFrame`; use `geometry=False` for a Polars table of the
attributes.

## Caching

Metadata (the catalog, schemas and lookup tables) is cached for the Python
session. Rows can also be cached on disk, if you ask:

```python
gcd.set_option("cache", True)  # or cache=True in gcd.rows()
```

Cached responses are kept with their `ETag` in the user cache folder, and
each repeat asks the server whether the data changed: an unchanged answer
reuses the saved copy without downloading, and a new data release downloads
afresh (a response the server marks fresh, for five minutes, is reused
without asking). `gcd.cache_clear()` empties both caches.
