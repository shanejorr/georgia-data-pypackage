"""Utilities: :func:`meta` and :func:`citation`."""

from __future__ import annotations

import re
from typing import Any

from . import _cache
from ._api import BASE_URL
from ._errors import gcd_error
from ._frames import attached, is_frame
from ._schema import dataset_schema, lookup_table_names


def meta(x: Any) -> dict[str, Any]:
    """Get the metadata carried by a result.

    Every data frame from :func:`rows` carries the response's metadata: what
    the rows are, where they come from and how to cite them. ``meta()``
    returns it. Results of :func:`search`, the zone functions and
    :func:`locate` carry their notes the same way.

    Polars data frames have no attributes, so the package keeps the metadata
    beside the object itself: read it from the result as it came back, since
    a new data frame derived from it (a filter, a join) doesn't carry it.
    pandas results also hold it in ``df.attrs["gcd_meta"]``, which pandas
    keeps through some operations. :func:`citation` also accepts a dataset
    name.

    Parameters
    ----------
    x : pandas.DataFrame or polars.DataFrame
        A result of :func:`rows` (or of :func:`search`, a zone function or
        :func:`locate`).

    Returns
    -------
    dict
        For :func:`rows`: ``dataset`` (the name), ``title``, ``detail``,
        ``key_metric``, ``units`` (each metric's unit), ``null_semantics``
        (what a missing value means), ``source``, ``source_url``,
        ``citation``, ``license``, ``schema`` (the schema's path),
        ``advisories`` (a list of ``{"code", "message"}`` dicts),
        ``year_meaning``, ``omitted_columns`` (columns left out because they
        were empty), ``data_version``, ``updated_at`` and ``request_url``.
        Fields the API didn't send are absent. For :func:`search`:
        ``confidence``, ``retrieval`` and ``total_matches``; for the zone
        functions and :func:`locate`: ``note`` (and ``assignment_note``).

    See Also
    --------
    citation : cite the data.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> grad = gcd.rows(
    ...     "graduation_rate_4_year_cohort", district="Fulton County",
    ...     year=2024, demographic="all",
    ... )  # doctest: +SKIP
    >>> gcd.meta(grad)["advisories"]  # doctest: +SKIP
    """
    info = attached(x) if is_frame(x) else None
    if info is None:
        raise gcd_error(
            "`x` carries no Georgia Civic Data metadata.",
            [
                "Metadata comes with results of gcd.rows(); a data frame derived "
                "from a result doesn't carry it.",
                "gcd.citation() also takes a dataset name.",
            ],
            code="no_metadata",
        )
    return info


def citation(x: Any) -> str:
    """Cite a dataset.

    The citation for data from Georgia Civic Data, ready to paste:

    "{title}. Georgia Civic Data (georgiacivicdata.org), CC BY 4.0.
    {dataset URL}. Original source: {source}."

    **License and attribution.** The data is published under the Creative
    Commons Attribution 4.0 International license (CC BY 4.0,
    https://creativecommons.org/licenses/by/4.0/). You may share and adapt it
    for any purpose, including commercially, as long as you give credit:
    name Georgia Civic Data (georgiacivicdata.org) and the original source,
    link the license, and say if you changed the data. The citation covers
    all three. The license covers Georgia Civic Data's cleaning,
    standardization, compilation and documentation; the source data stays
    under its original publisher's terms.

    Parameters
    ----------
    x : DataFrame or str
        A result of :func:`rows`, or a dataset name.

    Returns
    -------
    str
        The citation. For a result of :func:`rows` it is the API's own
        citation; for a name it is built from the dataset's schema in the
        same format.

    See Also
    --------
    meta : all the metadata.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.citation("graduation_rate_4_year_cohort")  # doctest: +SKIP
    """
    if isinstance(x, str):
        if x in lookup_table_names():
            raise gcd_error(
                f"{x!r} is a lookup table; cite the dataset that uses it.", code="no_citation"
            )
        schema = dataset_schema(x)
        title = schema.get("title") or _catalog_title(x)
        return format_citation(title, schema.get("name") or x, schema.get("source"))
    if not is_frame(x):
        raise TypeError("`x` must be a result of gcd.rows() or a dataset name.")
    info = meta(x)
    if isinstance(info.get("citation"), str):
        return str(info["citation"])
    return format_citation(info.get("title"), info.get("dataset"), info.get("source"))


def format_citation(title: str | None, name: str | None, source: str | None) -> str:
    """The citation in the platform's format."""
    source = source or "unknown"
    end = "" if re.search(r"[.!?]$", source) else "."
    return (
        f"{title or name}. Georgia Civic Data (georgiacivicdata.org), CC BY 4.0. "
        f"{BASE_URL}/datasets/{name}. Original source: {source}{end}"
    )


def _catalog_title(name: str) -> str | None:
    """A dataset's title from the (cached) catalog."""
    catalog = _cache.get_meta("datasets")
    for d in catalog.get("data") or []:
        if d.get("name") == name:
            return d.get("title")  # type: ignore[no-any-return]
    return None
