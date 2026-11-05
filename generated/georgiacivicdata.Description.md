# georgiacivicdata.Description

### *class* georgiacivicdata.Description(name, kind, title=None, summary=None, description=None, main_topic=None, source=None, source_url=None, update_frequency=None, updated_at=None, years=<factory>, year_gaps=<factory>, detail_levels=<factory>, default_detail=None, grain=<factory>, key_metric=None, primary_key=<factory>, search_columns=<factory>, crs=None, formats=<factory>, columns=None, filters=None, notes=<factory>, raw=<factory>, \_n_own=0, \_n_label=0, \_filter_params=<factory>, \_single=<factory>, \_column_names=<factory>)

Everything about one dataset, lookup table or geometry dataset.

Returned by [`describe()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe). `print()` (or the notebook display)
shows a readable summary; the attributes hold the parts.

* **Variables:**
  * **description** (*name* *,* *kind* *,* *title* *,* *summary* *,*) -- What it is. `kind` is `"table"`, `"geometry"` or `"lookup"`.
  * **update_frequency** (*main_topic* *,* *source* *,* *source_url* *,*) -- Where it comes from.
  * **updated_at** (*datetime.datetime* *or* *None*) -- When the data last changed (UTC).
  * **year_gaps** (*years* *,*) -- The years covered, and the years missing inside that span.
  * **key_metric** (*detail_levels* *,* *default_detail* *,* *grain* *,*) -- The detail levels (and the default), the columns that identify a
    row, and the headline metric.
  * **search_columns** (*primary_key* *,*) -- For lookup tables: the key, and the columns `q` searches.
  * **formats** (*crs* *,*) -- For geometry datasets: the coordinate system and download formats.
  * **columns** (*DataFrame*) -- The column dictionary, as [`columns()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns) returns it by default.
  * **filters** (*DataFrame*) -- Every filter parameter: `param`, `kind`, `values` (list
    column), `multi_value`, `has_total`, `total_value`,
    `requires_single_value` and `nullable`.
  * **notes** (*dict*) -- The contract's declarations that are present, each a data frame, a
    string or a dict (see [`describe()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)).
  * **raw** (*dict*) -- The full parsed schema response, without platform-internal fields.

#### \_\_init_\_(name, kind, title=None, summary=None, description=None, main_topic=None, source=None, source_url=None, update_frequency=None, updated_at=None, years=<factory>, year_gaps=<factory>, detail_levels=<factory>, default_detail=None, grain=<factory>, key_metric=None, primary_key=<factory>, search_columns=<factory>, crs=None, formats=<factory>, columns=None, filters=None, notes=<factory>, raw=<factory>, \_n_own=0, \_n_label=0, \_filter_params=<factory>, \_single=<factory>, \_column_names=<factory>)

### Methods

| [`__init__`](#georgiacivicdata.Description.__init__)(name, kind[, title, summary, ...])   |                                                                  |
|-------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| `format`([width])                                                                         | The summary as text, wrapped to `width` (default: the terminal). |
| `lines`()                                                                                 | The summary as lines of text (unwrapped).                        |

### Attributes

| `columns`          |    |
|--------------------|----|
| `crs`              |    |
| `default_detail`   |    |
| `description`      |    |
| `filters`          |    |
| `key_metric`       |    |
| `main_topic`       |    |
| `source`           |    |
| `source_url`       |    |
| `summary`          |    |
| `title`            |    |
| `update_frequency` |    |
| `updated_at`       |    |
| `name`             |    |
| `kind`             |    |
| `years`            |    |
| `year_gaps`        |    |
| `detail_levels`    |    |
| `grain`            |    |
| `primary_key`      |    |
| `search_columns`   |    |
| `formats`          |    |
| `notes`            |    |
| `raw`              |    |
