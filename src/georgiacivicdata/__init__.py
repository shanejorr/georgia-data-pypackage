"""georgiacivicdata: access public data from Georgia Civic Data.

A Python client for the Georgia Civic Data REST API at
https://georgiacivicdata.org/api/v1 (documentation:
https://georgiacivicdata.org/docs): cleaned public data about Georgia's
schools and communities, as pandas or Polars data frames with place names
beside codes, typed from each dataset's schema.

Find data
    :func:`datasets` (the catalog) and :func:`search` (ranked search from
    plain words).
Understand a dataset
    :func:`describe`, :func:`columns` and :func:`contract`.
Get data
    :func:`rows` (filtered rows, names beside codes) and :func:`values`
    (which category combinations exist, with row counts).
Lookup tables
    :func:`dimension`: districts, schools, counties, tracts, block groups and
    demographic groups, with their attributes.
Geography and school zones
    :func:`school_zones`, :func:`district_boundaries`,
    :func:`school_zone_status`, :func:`school_zone_coverage` and
    :func:`locate`.
Utilities
    :func:`meta`, :func:`citation`, :func:`cache_clear`, and the options
    :func:`set_option`, :func:`get_option` and :func:`option_context`.

**Missing values.** A missing metric usually means the value was
**suppressed** to protect privacy (small counts), not that it is zero.

**Data license.** The data is published under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/): credit "Georgia Civic Data
(georgiacivicdata.org)" and the original source; :func:`citation` writes the
citation. The package code is MIT-licensed.
"""

from ._cache import cache_clear
from ._catalog import datasets, search
from ._describe import Description, columns, contract, describe
from ._dimension import dimension
from ._errors import (
    GCDCensusError,
    GCDError,
    GCDNotFoundError,
    GCDPlaceAmbiguousError,
    GCDPlaceNotFoundError,
    GCDUnavailableError,
)
from ._locate import locate
from ._messages import GCDAdvisory
from ._meta import citation, meta
from ._options import get_option, option_context, set_option
from ._rows import rows
from ._values import values
from ._version import __version__
from ._zones import district_boundaries, school_zone_coverage, school_zone_status, school_zones

__all__ = [
    "Description",
    "GCDAdvisory",
    "GCDCensusError",
    "GCDError",
    "GCDNotFoundError",
    "GCDPlaceAmbiguousError",
    "GCDPlaceNotFoundError",
    "GCDUnavailableError",
    "__version__",
    "cache_clear",
    "citation",
    "columns",
    "contract",
    "datasets",
    "describe",
    "dimension",
    "district_boundaries",
    "get_option",
    "locate",
    "meta",
    "option_context",
    "rows",
    "school_zone_coverage",
    "school_zone_status",
    "school_zones",
    "search",
    "set_option",
    "values",
]
