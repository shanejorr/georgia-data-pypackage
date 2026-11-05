# georgiacivicdata.get_option

### georgiacivicdata.get_option(name)

Get the value of a package option.

* **Parameters:**
  **name** (*str*) -- One of `"backend"`, `"quiet"`, `"cache"` or `"cache_dir"`
  (see [`set_option()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.set_option.md#georgiacivicdata.set_option)).
* **Returns:**
  *Any* -- The option's current value.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> gcd.get_option("backend")
'pandas'
```
