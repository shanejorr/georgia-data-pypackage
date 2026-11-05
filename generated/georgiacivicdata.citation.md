# georgiacivicdata.citation

### georgiacivicdata.citation(x)

Cite a dataset.

The citation for data from Georgia Civic Data, ready to paste:

"{title}. Georgia Civic Data (georgiacivicdata.org), CC BY 4.0.
{dataset URL}. Original source: {source}."

**License and attribution.** The data is published under the Creative
Commons Attribution 4.0 International license (CC BY 4.0,
[https://creativecommons.org/licenses/by/4.0/](https://creativecommons.org/licenses/by/4.0/)). You may share and adapt it
for any purpose, including commercially, as long as you give credit:
name Georgia Civic Data (georgiacivicdata.org) and the original source,
link the license, and say if you changed the data. The citation covers
all three. The license covers Georgia Civic Data's cleaning,
standardization, compilation and documentation; the source data stays
under its original publisher's terms.

* **Parameters:**
  **x** (*DataFrame* *or* *str*) -- A result of [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows), or a dataset name.
* **Returns:**
  *str* -- The citation. For a result of [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) it is the API's own
  citation; for a name it is built from the dataset's schema in the
  same format.

#### SEE ALSO
[`meta`](https://georgiacivicdata.org/py/generated/georgiacivicdata.meta.md#georgiacivicdata.meta)
: all the metadata.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.citation("graduation_rate_4_year_cohort")
```
