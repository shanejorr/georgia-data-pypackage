# Reference

Every function, grouped as in the R package. Import the package as
`import georgiacivicdata as gcd`.

## Find data

| [`datasets`](https://georgiacivicdata.org/py/generated/georgiacivicdata.datasets.md#georgiacivicdata.datasets)   | List the datasets in the catalog.   |
|------------------------------------------------------------------------------------------------------------------|-------------------------------------|
| [`search`](https://georgiacivicdata.org/py/generated/georgiacivicdata.search.md#georgiacivicdata.search)         | Search the catalog.                 |

## Understand a dataset

| [`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)          | Describe a dataset or lookup table.                             |
|-------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| [`columns`](https://georgiacivicdata.org/py/generated/georgiacivicdata.columns.md#georgiacivicdata.columns)             | Get a dataset's column dictionary.                              |
| [`contract`](https://georgiacivicdata.org/py/generated/georgiacivicdata.contract.md#georgiacivicdata.contract)          | Get a dataset's data contract.                                  |
| [`Description`](https://georgiacivicdata.org/py/generated/georgiacivicdata.Description.md#georgiacivicdata.Description) | Everything about one dataset, lookup table or geometry dataset. |

## Get data

| [`rows`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows)       | Get rows of a dataset.                          |
|----------------------------------------------------------------------------------------------------------|-------------------------------------------------|
| [`values`](https://georgiacivicdata.org/py/generated/georgiacivicdata.values.md#georgiacivicdata.values) | List the category combinations a filter covers. |

## Lookup tables

| [`dimension`](https://georgiacivicdata.org/py/generated/georgiacivicdata.dimension.md#georgiacivicdata.dimension)   | Get the rows of a lookup table.   |
|---------------------------------------------------------------------------------------------------------------------|-----------------------------------|

## Geography and school zones

| [`school_zones`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zones.md#georgiacivicdata.school_zones)                         | Get school attendance zones.                  |
|----------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------|
| [`district_boundaries`](https://georgiacivicdata.org/py/generated/georgiacivicdata.district_boundaries.md#georgiacivicdata.district_boundaries)    | Get school district boundaries.               |
| [`school_zone_status`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zone_status.md#georgiacivicdata.school_zone_status)       | Get each school's attendance-zone status.     |
| [`school_zone_coverage`](https://georgiacivicdata.org/py/generated/georgiacivicdata.school_zone_coverage.md#georgiacivicdata.school_zone_coverage) | Get each district's attendance-zone coverage. |
| [`locate`](https://georgiacivicdata.org/py/generated/georgiacivicdata.locate.md#georgiacivicdata.locate)                                           | Locate points or addresses.                   |

## Utilities

| [`meta`](https://georgiacivicdata.org/py/generated/georgiacivicdata.meta.md#georgiacivicdata.meta)                               | Get the metadata carried by a result.             |
|----------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------|
| [`citation`](https://georgiacivicdata.org/py/generated/georgiacivicdata.citation.md#georgiacivicdata.citation)                   | Cite a dataset.                                   |
| [`cache_clear`](https://georgiacivicdata.org/py/generated/georgiacivicdata.cache_clear.md#georgiacivicdata.cache_clear)          | Clear the session cache and the disk cache.       |
| [`set_option`](https://georgiacivicdata.org/py/generated/georgiacivicdata.set_option.md#georgiacivicdata.set_option)             | Set a package option for the rest of the session. |
| [`get_option`](https://georgiacivicdata.org/py/generated/georgiacivicdata.get_option.md#georgiacivicdata.get_option)             | Get the value of a package option.                |
| [`option_context`](https://georgiacivicdata.org/py/generated/georgiacivicdata.option_context.md#georgiacivicdata.option_context) | Set options temporarily, inside a `with` block.   |

## Errors and advisories

API errors keep the API's own `code` (such as `"TOPIC_NOT_FOUND"`), the
HTTP `status` and the error's `details`. Catch `GCDError` for any of them,
or a subclass for one kind of failure.

| [`GCDError`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDError.md#georgiacivicdata.GCDError)                                           | Base class of every error from the Georgia Civic Data API or this package.                                                               |
|----------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| [`GCDNotFoundError`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDNotFoundError.md#georgiacivicdata.GCDNotFoundError)                   | No such dataset, lookup table or path (HTTP 404).                                                                                        |
| [`GCDUnavailableError`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDUnavailableError.md#georgiacivicdata.GCDUnavailableError)          | The service couldn't answer: no connection, a timeout, a rate limit that outlasted the retries, or a server error (HTTP 5xx).            |
| [`GCDPlaceNotFoundError`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDPlaceNotFoundError.md#georgiacivicdata.GCDPlaceNotFoundError)    | A district, school or county name matched nothing.                                                                                       |
| [`GCDPlaceAmbiguousError`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDPlaceAmbiguousError.md#georgiacivicdata.GCDPlaceAmbiguousError) | A district, school or county name matched more than one place.                                                                           |
| [`GCDCensusError`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDCensusError.md#georgiacivicdata.GCDCensusError)                         | The U.S.                                                                                                                                 |
| [`GCDAdvisory`](https://georgiacivicdata.org/py/generated/georgiacivicdata.GCDAdvisory.md#georgiacivicdata.GCDAdvisory)                                  | An advisory about a result: suppressed values, totals that must not be added to their subgroups, a search with no good match, and so on. |
