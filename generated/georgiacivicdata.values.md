# georgiacivicdata.values

### georgiacivicdata.values(name, columns, \*, year=None, detail=None, district=None, school=None, county=None, backend=None, \*\*filters)

List the category combinations a filter covers.

Which combinations of category values exist, and how many rows each has,
under the same filters as [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows). It answers "which subjects exist
in 2016 at district level?" or "which demographic groups does this county
have rows for?" without downloading the rows. The schema's
`valid_values` list every value a column has ever used; `values()`
lists what exists **for this filter**, which is what you need when a
filter returns zero rows.

The API returns at most 500 combinations; the function warns when that
cap is reached.

* **Parameters:**
  * **name** (*str*) -- The dataset's name.
  * **columns** (*str* *or* *list* *of* *str*) -- One or more categorical columns (or `"demographic"`), such as
    `"subject"` or `["subject", "grade_cluster"]`.
  * **year** -- Exactly as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows).
  * **detail** -- Exactly as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows).
  * **district** -- Exactly as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows).
  * **school** -- Exactly as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows).
  * **county** -- Exactly as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows).
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option.
  * **\*\*filters** -- Named filters, exactly as in [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows).
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- Most rows first, one column per requested column (typed from the
  schema; missing where the column is empty for those rows) and
  `n_rows` (integer), the number of rows with that combination.

#### SEE ALSO
[`rows`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows)
: the rows themselves.

[`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)
: every filter and its allowed values.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.values(
...     "ccrpi_content_mastery", "subject", year=2016, detail="districts"
... )
>>> gcd.values(
...     "graduation_rate_4_year_cohort", "demographic",
...     district="Fulton County", year=2024,
... )
```
