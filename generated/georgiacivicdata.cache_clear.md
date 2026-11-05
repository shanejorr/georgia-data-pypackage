# georgiacivicdata.cache_clear

### georgiacivicdata.cache_clear()

Clear the session cache and the disk cache.

Empties the in-memory cache of metadata (the catalog, dataset schemas and
lookup tables) kept for the Python session, and deletes the opt-in disk
cache of row downloads (see the `cache` argument of [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows)).
Location lookups are never cached, so there is nothing to clear for them.

The disk cache lives in the standard user cache folder for
`georgiacivicdata` (or the `cache_dir` option). It is only ever
written when you ask for it, with `cache=True` or
`set_option("cache", True)`.

* **Returns:**
  *None*

#### SEE ALSO
[`rows`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows)
: the disk cache.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.cache_clear()
```
