# Get started

`georgiacivicdata` reads the [Georgia Civic Data](https://georgiacivicdata.org)
API: cleaned public data about Georgia's schools and communities. The
[home page](https://georgiacivicdata.org/py/index.md) walks through the basic workflow (search for a
dataset, read its columns, get its rows, plot them and cite them) with
Fulton County's graduation rate. This article covers what that example
leaves out: how to narrow the catalog, how names and filters work, and the
rules of the data that are easy to get wrong.

```python
import georgiacivicdata as gcd
```

## Browse the catalog

`gcd.datasets()` is the whole catalog, one row per dataset. Every argument
narrows it on the server:

```python
catalog = gcd.datasets()
catalog.groupby(["main_topic", "kind"]).size()
```

```text
main_topic   kind    
census       table       28
education    geometry     2
             table       61
health       table       62
immigration  table       23
dtype: int64
```

```python
gcd.datasets(main_topic="education", level="districts", year=2025)[["name", "title"]].head()
```

```text
                         name                         title
0       ccrpi_content_mastery         CCRPI Content Mastery
1       ccrpi_graduation_rate  High School Graduation Rates
2              ccrpi_progress                CCRPI Progress
3             ccrpi_readiness               CCRPI Readiness
4  ccrpi_scoring_by_component   CCRPI Scores and Components
```

## Read a dataset's notes

`gcd.describe()` prints what a dataset holds, where it comes from, its years
and detail levels, the columns that identify a row (its *grain*) and the
notes its data contract declares:

```python
gcd.describe("graduation_rate_4_year_cohort")
```

```text
-- Four-Year Cohort Graduation Rate (graduation_rate_4_year_cohort) ------------
Share of the four-year high school cohort that graduated, by school, district,
and state and demographic subgroup, 2004-2025.

Source: Governor's Office of Education and Workforce Strategy (GOEWS, formerly
GOSA)
Years: 2004-2025
Detail levels: districts, schools (default), states
Grain: year, district_code, school_code, demographic
Key metric: graduation_rate
Columns: 7, plus 6 joined name columns (see .columns); filters: 18 (see
.filters)

-- Notes -----------------------------------------------------------------------
* Missing values: missing means suppressed (small counts), not zero; zeros are
  real from 2010 on.
* Limitations: 2004-2010 figures predate Georgia's adoption of the federal four-
  year adjusted-cohort methodology (ACGR, first reported 2011) and use the
  state's earlier leaver-based rate; the 2010->2011 state rate drop (~81% to
  ~67%) is a methodology break, not a real decline — do not trend across it.
  Suppressed cells are NULL (not zero) from 2010 onward, but 2004-2009 sources
  use literal ZEROS for suppressed cells — a zero rate/count in those years may
  be real or suppressed and cannot be distinguished; treat very small cohorts in
  2004-2009 with caution. num_cohort is NULL for every row in 2012-2016 (the
  source publishes no denominator in those years). The 2004 file lists every
  public school, including elementary and middle schools with no graduating
  cohort, so 1,703 of its 2,037 all-students school rows have no graduate count
  or rate; from 2005 only schools with a graduating cohort are listed (344 in
  2005). School rows do not always sum to the published district row: of the
  42,815 district rows (all subgroups) with a published num_graduates and at
  least one published school value, 468 publish a district num_graduates below
  the sum of its school rows, 49 of them among the 4,039 all-students rows
  (source-published, 2005-2025; e.g. 2016 Whitfield 709 vs 810, 2014 Richmond
  economically_disadvantaged 582 vs 1,286) — use the official district/state
  rows for rollups rather than summing school rows. economically_disadvantaged
  is not a like-for-like group across years. Statewide it is 55-56% of the
  cohort in 2017-2021, then 47% (2022), 53% (2023), 61% (2024) and 66% (2025),
  and district coding shifts: Cobb County puts 98% of its 2021 cohort in the
  group (36-38% in 2017-2020 and 2023, 20% in 2022) and under 2% of its
  graduates in 2011, 2012 and 2014, and districts with 100+ graduates that
  report 10% or less of them in the group or suppress it number 6-11 a year in
  2021-2023 (0-2 a year in 2016-2020). GOEWS does not document these shifts. The
  group's graduation rate moves when its membership does, so check its share of
  the cohort before comparing it across years or districts. The race axis uses
  the combined asian_pacific_islander bucket — not comparable row-for-row with
  split-convention topics without aggregating those topics' asian +
  pacific_islander rows at query time. State rows have NULL district_code and
  school_code; district rows have NULL school_code.
* Series break in 2011: From 2011 Georgia reports the federal four-year
  adjusted-cohort graduation rate, while 2004-2010 use the state's earlier
  leaver-based count, so the state rate falls from 0.808 (2010) to 0.675 (2011)
  and the cohort rises from 113,364 to 131,012 because the method changed, not
  because fewer students graduated.
```

Some categorical columns have no total. `gcd.describe()` lists them under
**"Pick one value of"**: for example, `grade_cluster` and `subject` in
`ccrpi_content_mastery`, whose values must not be mixed in one summary. The
result's `filters` table shows every filter:

```python
d = gcd.describe("ccrpi_content_mastery")
d.filters.loc[d.filters["kind"] == "categorical", ["param", "has_total", "requires_single_value"]]
```

```text
              param  has_total  requires_single_value
8     grade_cluster      False                   True
9   assessment_type      False                  False
10          subject      False                   True
11       ccrpi_flag      False                  False
```

## Filter by name or by code

Name a district, school or county and the package turns it into a code.
Names match exactly, ignoring case, accents and a trailing "County", and
former names work too:

```python
gcd.rows(
    "graduation_rate_4_year_cohort",
    district="Fulton County",
    school="Riverwood High School",  # a former name
    demographic="all",
    year=range(2021, 2026),
    quiet=True,
)[["year", "district_code", "school_code", "school_name", "graduation_rate"]]
```

```text
   year district_code school_code                             school_name  graduation_rate
0  2021           660        3066  Riverwood International Charter School           0.9345
1  2022           660        3066  Riverwood International Charter School           0.9753
2  2023           660        3066  Riverwood International Charter School           0.9693
3  2024           660        3066  Riverwood International Charter School           0.9877
4  2025           660        3066  Riverwood International Charter School           0.9708
```

A name that matches more than one place stops with the candidates instead
of guessing. "Eastside Elementary School" is in several districts, and
Fulton County has an old and a new "Milton High School". The error is a
`GCDPlaceAmbiguousError`, so a script can catch it:

```python
try:
    gcd.rows("graduation_rate_4_year_cohort", school="Milton High School", district="Fulton County")
except gcd.GCDPlaceAmbiguousError as err:
    print(err)
```

```text
'Milton High School' matches more than one school.
  Use `school_id` with one 'DISTRICT-SCHOOL' code.
  * 660-0106: Milton High School (Fulton County, active)
  * 660-2060: Milton High School (Fulton County, inactive)
```

Codes work everywhere names do. A school is identified by its district and
school codes together, written `"DISTRICT-SCHOOL"` in `school_id`:

```python
gcd.rows(
    "graduation_rate_4_year_cohort",
    school_id="660-0106",
    demographic="all",
    year=2025,
    quiet=True,
)[["year", "school_code", "school_name", "num_graduates", "num_cohort", "graduation_rate"]]
```

```text
   year school_code         school_name  num_graduates  num_cohort  graduation_rate
0  2025        0106  Milton High School            502         522           0.9617
```

## Years and detail levels

`year=range(2021, 2026)` asks for 2021 to 2025 (a Python range leaves out its
end); `year=[2015, 2025]` asks for those two years only. Each call returns
one **detail level**: schools, districts, states, counties or tracts,
whatever the dataset publishes. The default is the finest level (counties
for Census datasets). Columns that would be empty at a level are left out:

```python
gcd.rows(
    "graduation_rate_4_year_cohort",
    detail="states",
    demographic="all",
    year=[2015, 2025],
    quiet=True,
)
```

```text
   year demographic demographic_label demographic_category  num_graduates  num_cohort  \
0  2015         all               All            aggregate          98465        <NA>   
1  2025         all               All            aggregate         123911      142070   

   graduation_rate  
0           0.7884  
1           0.8722  
```

To combine levels, call once per level and concatenate the rows
(`pd.concat`).

## What a missing value means

A missing metric usually means the value was **suppressed** to protect
privacy (small counts), **not zero**. The schema's `null_semantics` says
which, and `gcd.rows()` passes on the API's advisory when a result holds
suppressed values:

```python
small = gcd.rows(
    "graduation_rate_4_year_cohort",
    district="Appling County",
    year=2024,
    detail="districts",
)
small[["demographic", "num_graduates", "num_cohort", "graduation_rate"]].head()
```

```text
GCDAdvisory: This result contains NULL metric cells, which mean the value was SUPPRESSED (small counts), not zero — do not report or chart a NULL as 0 (see null_semantics and each column's null_meaning).
GCDAdvisory: Demographic groups overlap across categories and may overlap within a category (active_duty can be a subset of military_connected). Read the dataset's definitions and non_additive declarations. Use the published `all` total when available, never add it to its subgroups. Counts reconcile only for complete, disjoint groups; subgroup rates generally do not add to the overall rate.
GCDAdvisory: `district_census_id` is a 5-digit Census school-district code, NOT a county FIPS, and a district is not 1:1 with a county — do not map these district rows as counties.
```

```text
                  demographic  num_graduates  num_cohort  graduation_rate
0                 active_duty           <NA>        <NA>              NaN
1                         all            225         240           0.9375
2      asian_pacific_islander           <NA>        <NA>              NaN
3                       black             57          62           0.9194
4  economically_disadvantaged            225         240           0.9375
```

The advisories are `GCDAdvisory` warnings. They stay with the result in
`gcd.meta(small)["advisories"]`; `quiet=True` (or
`gcd.set_option("quiet", True)`) silences them, and the usual
[`warnings`](https://docs.python.org/3/library/warnings.html) filters work too:

```python
[a["code"] for a in gcd.meta(small)["advisories"]]
```

```text
['suppressed_values_present',
 'demographic_non_additive',
 'district_not_county']
```

## Totals beside subgroups

Nothing is pinned by default, so a result holds the `all` total beside every
subgroup, and subgroups from different categories overlap (a student is in a
race group, a gender group and an economic group at once). Never add them
up:

```python
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

```text
published_total      7934
sum_of_every_row    39902
dtype: int64
```

Use the published `all` row for totals, and filter one category
(`demographic_category="race"`) to compare groups.

## Which values exist: `gcd.values()`

When a filter returns nothing, `gcd.values()` shows which combinations exist
under the other filters, with row counts, without downloading rows:

```python
combos = gcd.values(
    "ccrpi_content_mastery", ["grade_cluster", "subject"], year=2025, detail="districts"
)
combos.head()
```

```text
  grade_cluster                subject  n_rows
0    elementary  english_language_arts    2340
1    elementary            mathematics    2340
2    elementary                science    2340
3          high  english_language_arts    2340
4          high            mathematics    2340
```

## Lookup tables

There are six lookup tables: `districts`, `schools`, `counties`, `tracts`,
`block_groups` and `demographics`. `gcd.dimension()` returns any of them.
**School codes repeat across districts**, so join schools on
`district_code` and `school_code` together, never `school_code` alone:

```python
schools = gcd.dimension("schools", columns=["district_code", "school_code"])
schools["school_code"].value_counts().head(3)
```

```text
school_code
8010    198
8012    175
8013    166
Name: count, dtype: int64[pyarrow]
```

## pandas or Polars

pandas is the default. Pass `backend="polars"` to any table function, or set
it for the session:

```python
gcd.set_option("backend", "polars")
gcd.dimension("counties", n_max=3)
```

```text
shape: (3, 2)
┌─────────────┬─────────────┐
│ county_fips ┆ county_name │
│ ---         ┆ ---         │
│ str         ┆ str         │
╞═════════════╪═════════════╡
│ 13001       ┆ Appling     │
│ 13003       ┆ Atkinson    │
│ 13005       ┆ Bacon       │
└─────────────┴─────────────┘
```

```python
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
