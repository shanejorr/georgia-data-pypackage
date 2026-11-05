# georgiacivicdata.describe

### georgiacivicdata.describe(name, \*, backend=None)

Describe a dataset or lookup table.

Everything about one dataset, lookup table or geometry dataset: what it
holds, its source, years, detail levels, the columns that identify a row
(the grain), its key metric, every filter, and the notes its data
contract declares (limitations, series breaks, groups that must not be
added up, and so on). Printing the result shows a readable summary.

Read the **"Pick one value of"** line: it names categorical columns with
no total (such as `grade_cluster`), whose values must not be mixed in
one summary. [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) returns every value of them unless you filter
one.

The `filters` table is also how to discover the filters that are not
columns of the dataset: lookup-table attributes such as
`district_type`, `school_level`, `locale` and
`demographic_category`.

* **Parameters:**
  * **name** (*str*) -- A dataset, lookup table or geometry dataset name, such as
    `"graduation_rate_4_year_cohort"`, `"schools"` or
    `"school_attendance_zones"`. Names are unique across all three
    kinds.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame for the `columns`, `filters` and table
    `notes`. Default: the `backend` option.
* **Returns:**
  *Description* -- Attributes include `name`, `kind` (`"table"`, `"geometry"` or
  `"lookup"`), `title`, `summary`, `description`, `source`,
  `source_url`, `years`, `year_gaps`, `detail_levels`,
  `default_detail`, `grain`, `key_metric`, and:
  - `columns`: the column dictionary, as [`columns()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns) returns it
    by default (for a dataset, the joined name columns included).
  - `filters`: a data frame of every filter parameter: `param`,
    `kind` (categorical, foreign_key, dimension_attribute,
    metric_bound, year, detail, ...), `values` (list column of
    allowed values), `multi_value`, `has_total`, `total_value`,
    `requires_single_value` and `nullable`.
  - `notes`: the contract's declarations that are present:
    `limitations`, `year_meaning` (strings), `null_semantics` (a
    dict), `series_breaks`, `non_additive`, `partitions`,
    `pooled_rates`, `year_window`, `value_implications`,
    `pooled_min_count` (data frames), and `assignment_note` for the
    zones.
  - `raw`: the full parsed schema response.

#### SEE ALSO
[`columns`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns)
: the column table alone.

[`values`](https://georgiacivicdata.org/py/generated/georgiacivicdata.values.md#georgiacivicdata.values)
: the category values present under a filter.

[`contract`](https://georgiacivicdata.org/py/generated/georgiacivicdata.contract.md#georgiacivicdata.contract)
: the formal contract.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.describe("graduation_rate_4_year_cohort")
>>> gcd.describe("ccrpi_content_mastery").filters
>>> gcd.describe("schools")
```
