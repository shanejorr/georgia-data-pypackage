# georgiacivicdata.meta

### georgiacivicdata.meta(x)

Get the metadata carried by a result.

Every data frame from [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) carries the response's metadata: what
the rows are, where they come from and how to cite them. `meta()`
returns it. Results of [`search()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.search.md#georgiacivicdata.search), the zone functions and
[`locate()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.locate.md#georgiacivicdata.locate) carry their notes the same way.

Polars data frames have no attributes, so the package keeps the metadata
beside the object itself: read it from the result as it came back, since
a new data frame derived from it (a filter, a join) doesn't carry it.
pandas results also hold it in `df.attrs["gcd_meta"]`, which pandas
keeps through some operations. [`citation()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.citation.md#georgiacivicdata.citation) also accepts a dataset
name.

* **Parameters:**
  **x** (*pandas.DataFrame* *or* *polars.DataFrame*) -- A result of [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) (or of [`search()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.search.md#georgiacivicdata.search), a zone function or
  [`locate()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.locate.md#georgiacivicdata.locate)).
* **Returns:**
  *dict* -- For [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows): `dataset` (the name), `title`, `detail`,
  `key_metric`, `units` (each metric's unit), `null_semantics`
  (what a missing value means), `source`, `source_url`,
  `citation`, `license`, `schema` (the schema's path),
  `advisories` (a list of `{"code", "message"}` dicts),
  `year_meaning`, `omitted_columns` (columns left out because they
  were empty), `data_version`, `updated_at` and `request_url`.
  Fields the API didn't send are absent. For [`search()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.search.md#georgiacivicdata.search):
  `confidence`, `retrieval` and `total_matches`; for the zone
  functions and [`locate()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.locate.md#georgiacivicdata.locate): `note` (and `assignment_note`).

#### SEE ALSO
[`citation`](https://georgiacivicdata.org/py/generated/georgiacivicdata.citation.md#georgiacivicdata.citation)
: cite the data.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> grad = gcd.rows(
...     "graduation_rate_4_year_cohort", district="Fulton County",
...     year=2024, demographic="all",
... )
>>> gcd.meta(grad)["advisories"]
```
