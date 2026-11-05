# georgiacivicdata.set_option

### georgiacivicdata.set_option(name, value)

Set a package option for the rest of the session.

* **Parameters:**
  * **name** (*str*) -- 

    The option:
    - `"backend"`: `"pandas"` (default) or `"polars"`, the kind of
      data frame every table function returns when its `backend`
      argument is not given.
    - `"quiet"`: `True` silences the advisories of [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) and
      the notes of the search and zone functions. Default `False`.
    - `"cache"`: `True` turns on the disk cache of [`rows()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md#georgiacivicdata.rows) (see
      that function). Default `False`.
    - `"cache_dir"`: where the disk cache lives. Default `None`: the
      standard user cache folder for `georgiacivicdata`.
  * **value** (*Any*) -- The new value.
* **Returns:**
  *None*

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.set_option("backend", "polars")
>>> gcd.set_option("backend", "pandas")
```
