# georgiacivicdata.option_context

### georgiacivicdata.option_context(\*\*options)

Set options temporarily, inside a `with` block.

* **Parameters:**
  **\*\*options** (*Any*) -- Options and their values, as in [`set_option()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.set_option.md#georgiacivicdata.set_option).
* **Returns:**
  *contextmanager* -- A context manager that restores the previous values on exit.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> with gcd.option_context(backend="polars", quiet=True):
...     gcd.get_option("backend")
'polars'
```
