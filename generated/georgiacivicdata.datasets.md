# georgiacivicdata.datasets

### georgiacivicdata.datasets(main_topic=None, level=None, year=None, kind=None, details=False, \*, backend=None)

List the datasets in the catalog.

The catalog of everything the API publishes, one row per dataset. With
no arguments it returns **every dataset**: all subject areas, detail
levels and years, tables and geometry alike. Each argument only narrows
the list (the filtering runs on the server). About 176 datasets: small
enough to browse or filter locally.

The six lookup tables (districts, schools, counties, tracts, block
groups, demographics) are not datasets and are not listed; see
[`dimension()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.dimension.md#georgiacivicdata.dimension).

* **Parameters:**
  * **main_topic** (*str* *,* *optional*) -- A single subject area: `"education"`, `"census"`, `"health"` or
    `"immigration"`. Default: all.
  * **level** (*str* *,* *optional*) -- Keep datasets that publish rows at this detail level, such as
    `"schools"`, `"districts"`, `"counties"` or `"tracts"`.
    Default: all.
  * **year** (*int* *,* *optional*) -- Keep datasets that cover this year. Default: all.
  * **kind** ( *{"table"* *,*  *"geometry"}* *,* *optional*) -- Default: both.
  * **details** (*bool* *,* *default False*) -- `False` gives the compact catalog. `True` adds the long columns
    (description, source, grain and more).
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option.
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- One row per dataset, with columns:
  - `name`: the dataset's name, used by every other function.
  - `title`, `summary`: what it holds.
  - `kind`: `"table"` or `"geometry"`.
  - `main_topic`: the subject area.
  - `detail_levels`: list column of the levels it publishes.
  - `year_min`, `year_max`: integers, the years covered.

  With `details=True`, also: `description`, `source`,
  `source_url`, `grain` (list column: the columns that identify a
  row), `default_detail`, `year_gaps` (list column of missing
  years), `update_frequency`, `search_aliases_en` and
  `search_aliases_es` (list columns of everyday search phrases), and
  `updated_at` (UTC timestamp). Geometry datasets have missing values
  where a field doesn't apply.

#### SEE ALSO
[`search`](https://georgiacivicdata.org/py/generated/georgiacivicdata.search.md#georgiacivicdata.search)
: rank datasets by plain words.

[`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)
: one dataset.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.datasets()
>>> gcd.datasets(main_topic="education", level="schools")
>>> gcd.datasets(kind="geometry", details=True)
```
