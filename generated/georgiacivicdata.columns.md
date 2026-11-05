# georgiacivicdata.columns

### georgiacivicdata.columns(name, labels=True, \*, backend=None)

Get a dataset's column dictionary.

The columns of a dataset, lookup table or geometry dataset as a tidy
table: what each column means, its type, its unit and, for metrics,
whether it is a numerator or denominator. This is the place to check
"what does `pct_proficient_learner_or_above` mean, and is it 0-1?".

The dictionary lists every column a dataset can return. Which ones a
given [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) call returns also depends on its `detail` and
`columns`: code columns that would be empty on every row (a county
row's `tract_geoid`, a district row's `school_code`) are left out.

* **Parameters:**
  * **name** (*str*) -- A dataset, lookup table or geometry dataset name.
  * **labels** (*bool* *,* *default True*) -- `True` also lists the name columns that [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) joins in by
    default (`district_name`, `county_name`, `demographic_label`,
    ...), each right after its code, with `role` `"label"`.
    `False` lists the dataset's own columns only, matching
    `rows(labels=False)`. Labels come only with datasets; lookup tables
    and geometry datasets ignore this argument.
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option.
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- One row per column, with columns:
  - `column`: the column name.
  - `label`: a short display name.
  - `type`: `"integer"`, `"number"`, `"string"`, `"boolean"`
    or `"date"`, which [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) maps to integer, float, string,
    boolean and date columns.
  - `role`: `"year"`, a foreign key (`"fk_district"`,
    `"fk_school"`, ...), `"categorical"`, `"metric"` or
    `"label"` (a joined name column) for datasets; `"key"` or
    `"attribute"` for lookup tables.
  - `label_of`: for a `"label"` column, the code column it names
    (`"district_code"`, `"demographic"`, ...); otherwise missing.
  - `unit`: `"count"`, `"proportion"` (0-1 scale), a rate unit,
    ...
  - `is_key_metric`: boolean, true for the dataset's headline metric.
  - `metric_component`: `"numerator"` or `"denominator"` for the
    counts a rate is built from.
  - `nullable`: boolean.
  - `valid_values`: list column of a categorical column's values.
  - `description`: the full definition.
  - `null_meaning`: what a missing value means in this column.

  Fields that don't apply (labels and units for lookup tables and
  joined name columns, most fields for geometry datasets) are missing.
  A joined name column's `description` and `nullable` come from its
  lookup table; see [`dimension()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.dimension.md#georgiacivicdata.dimension).

#### SEE ALSO
[`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)
: the whole schema.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.columns("graduation_rate_4_year_cohort")
>>> gcd.columns("graduation_rate_4_year_cohort", labels=False)
>>> gcd.columns("schools")
```
