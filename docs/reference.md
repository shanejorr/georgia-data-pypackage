# Reference

Every function, grouped as in the R package. Import the package as
`import georgiacivicdata as gcd`.

```{eval-rst}
.. currentmodule:: georgiacivicdata
```

## Find data

```{eval-rst}
.. autosummary::
   :toctree: generated
   :nosignatures:

   datasets
   search
```

## Understand a dataset

```{eval-rst}
.. autosummary::
   :toctree: generated
   :nosignatures:

   describe
   columns
   contract
   Description
```

## Get data

```{eval-rst}
.. autosummary::
   :toctree: generated
   :nosignatures:

   rows
   values
```

## Lookup tables

```{eval-rst}
.. autosummary::
   :toctree: generated
   :nosignatures:

   dimension
```

## Geography and school zones

```{eval-rst}
.. autosummary::
   :toctree: generated
   :nosignatures:

   school_zones
   district_boundaries
   school_zone_status
   school_zone_coverage
   locate
```

## Utilities

```{eval-rst}
.. autosummary::
   :toctree: generated
   :nosignatures:

   meta
   citation
   cache_clear
   set_option
   get_option
   option_context
```

## Errors and advisories

API errors keep the API's own `code` (such as `"TOPIC_NOT_FOUND"`), the
HTTP `status` and the error's `details`. Catch `GCDError` for any of them,
or a subclass for one kind of failure.

```{eval-rst}
.. autosummary::
   :toctree: generated
   :nosignatures:

   GCDError
   GCDNotFoundError
   GCDUnavailableError
   GCDPlaceNotFoundError
   GCDPlaceAmbiguousError
   GCDCensusError
   GCDAdvisory
```
