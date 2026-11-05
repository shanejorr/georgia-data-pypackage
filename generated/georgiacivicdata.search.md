# georgiacivicdata.search

### georgiacivicdata.search(query, main_topic=None, level=None, year=None, n=20, \*, quiet=False, backend=None)

Search the catalog.

Ranked dataset search from plain words, in English or Spanish ("jobless
rate", "kids missing school", "desempleo"). Use it when you know what
you are looking for but not what the dataset is called.

Search is hybrid: keyword matching plus matching by meaning. The query
text is sent to the Georgia Civic Data API, which embeds it with Voyage
AI for the meaning half and never logs it. This is the one function
whose results can't be reproduced by filtering [`datasets()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets)
locally, and the ranking can change between releases of the platform.

* **Parameters:**
  * **query** (*str*) -- Plain words.
  * **main_topic** (*optional*) -- The same filters as [`datasets()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets): a subject area, a detail level
    and a year. Default: no filter.
  * **level** (*optional*) -- The same filters as [`datasets()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets): a subject area, a detail level
    and a year. Default: no filter.
  * **year** (*optional*) -- The same filters as [`datasets()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets): a subject area, a detail level
    and a year. Default: no filter.
  * **n** (*int* *,* *default 20*) -- The number of matches to return, 1 to 100.
  * **quiet** (*bool* *,* *default False*) -- `True` silences the notes on the search (see Returns).
  * **backend** ( *{"pandas"* *,*  *"polars"}* *,* *optional*) -- The kind of data frame to return. Default: the `backend` option.
* **Returns:**
  *pandas.DataFrame or polars.DataFrame* -- One row per match, best first, with columns:
  - `rank`: integer, 1 is the best match.
  - `name`, `title`, `summary`, `main_topic`: the dataset.
  - `detail_levels`: list column of the levels it publishes.
  - `year_min`, `year_max`: integers, the years covered.
  - `score`: float, the match score.
  - `matched_on`: list column of what matched (aliases, columns,
    summary, ...).
  - `matched_columns`: list column of the dataset's columns that
    matched.

  [`meta()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.meta.md#georgiacivicdata.meta) on the result gives `confidence` (`"high"`,
  `"medium"` or `"low"`), `retrieval` (a dict: `mode` and
  `reranked`) and `total_matches`. On low confidence the function
  advises that nothing in the catalog may fit; it also names any lookup
  tables that matched.

#### SEE ALSO
[`datasets`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets)
: the full catalog.

[`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe), [`columns`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns)

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.search("high school graduation")
>>> gcd.search("desempleo", n=5)
>>> gcd.search("chronic absence", level="districts")
```
