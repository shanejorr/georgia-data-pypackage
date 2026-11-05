"""Find data: the catalog (:func:`datasets`) and ranked search (:func:`search`)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, overload

import pandas as pd
import pyarrow as pa

from . import _cache
from ._api import get_json
from ._frames import Frame, records_to_table, to_frame
from ._messages import advise
from ._options import is_quiet, resolve_backend
from ._params import check_flag, format_number
from ._schema import apply_schema_types, drop_internal

if TYPE_CHECKING:
    import polars as pl

COMPACT_FIELDS = (
    "name",
    "title",
    "summary",
    "kind",
    "main_topic",
    "detail_levels",
    "year_min",
    "year_max",
)
FULL_FIELDS = (
    "description",
    "source",
    "source_url",
    "grain",
    "default_detail",
    "year_gaps",
    "update_frequency",
    "search_aliases_en",
    "search_aliases_es",
    "updated_at",
)
CATALOG_TYPES = {
    "name": "string",
    "title": "string",
    "summary": "string",
    "kind": "string",
    "main_topic": "string",
    "year_min": "integer",
    "year_max": "integer",
    "description": "string",
    "source": "string",
    "source_url": "string",
    "default_detail": "string",
    "update_frequency": "string",
    "updated_at": "timestamp",
}


@overload
def datasets(
    main_topic: str | None = ...,
    level: str | None = ...,
    year: int | None = ...,
    kind: Literal["table", "geometry"] | None = ...,
    details: bool = ...,
    *,
    backend: Literal["pandas"],
) -> pd.DataFrame: ...
@overload
def datasets(
    main_topic: str | None = ...,
    level: str | None = ...,
    year: int | None = ...,
    kind: Literal["table", "geometry"] | None = ...,
    details: bool = ...,
    *,
    backend: Literal["polars"],
) -> pl.DataFrame: ...
@overload
def datasets(
    main_topic: str | None = ...,
    level: str | None = ...,
    year: int | None = ...,
    kind: Literal["table", "geometry"] | None = ...,
    details: bool = ...,
    *,
    backend: None = ...,
) -> Frame: ...
def datasets(
    main_topic: str | None = None,
    level: str | None = None,
    year: int | None = None,
    kind: Literal["table", "geometry"] | None = None,
    details: bool = False,
    *,
    backend: Literal["pandas", "polars"] | None = None,
) -> Frame:
    """List the datasets in the catalog.

    The catalog of everything the API publishes, one row per dataset. With
    no arguments it returns **every dataset**: all subject areas, detail
    levels and years, tables and geometry alike. Each argument only narrows
    the list (the filtering runs on the server). About 176 datasets: small
    enough to browse or filter locally.

    The six lookup tables (districts, schools, counties, tracts, block
    groups, demographics) are not datasets and are not listed; see
    :func:`dimension`.

    Parameters
    ----------
    main_topic : str, optional
        A single subject area: ``"education"``, ``"census"``, ``"health"`` or
        ``"immigration"``. Default: all.
    level : str, optional
        Keep datasets that publish rows at this detail level, such as
        ``"schools"``, ``"districts"``, ``"counties"`` or ``"tracts"``.
        Default: all.
    year : int, optional
        Keep datasets that cover this year. Default: all.
    kind : {"table", "geometry"}, optional
        Default: both.
    details : bool, default False
        ``False`` gives the compact catalog. ``True`` adds the long columns
        (description, source, grain and more).
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        One row per dataset, with columns:

        - ``name``: the dataset's name, used by every other function.
        - ``title``, ``summary``: what it holds.
        - ``kind``: ``"table"`` or ``"geometry"``.
        - ``main_topic``: the subject area.
        - ``detail_levels``: list column of the levels it publishes.
        - ``year_min``, ``year_max``: integers, the years covered.

        With ``details=True``, also: ``description``, ``source``,
        ``source_url``, ``grain`` (list column: the columns that identify a
        row), ``default_detail``, ``year_gaps`` (list column of missing
        years), ``update_frequency``, ``search_aliases_en`` and
        ``search_aliases_es`` (list columns of everyday search phrases), and
        ``updated_at`` (UTC timestamp). Geometry datasets have missing values
        where a field doesn't apply.

    See Also
    --------
    search : rank datasets by plain words.
    describe : one dataset.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.datasets()  # doctest: +SKIP
    >>> gcd.datasets(main_topic="education", level="schools")  # doctest: +SKIP
    >>> gcd.datasets(kind="geometry", details=True)  # doctest: +SKIP
    """
    resolve_backend(backend)
    _check_catalog_filters(main_topic, level, year)
    if kind is not None and kind not in ("table", "geometry"):
        raise ValueError("`kind` must be 'table' or 'geometry'.")
    check_flag(details, "details")
    query: dict[str, list[str]] = {}
    for name, value in (("main_topic", main_topic), ("level", level), ("kind", kind)):
        if value is not None:
            query[name] = [value]
    if year is not None:
        query["year"] = [format_number(year)]
    if details:
        query["fields"] = ["full"]
    catalog = _cache.get_meta("datasets", query)
    return to_frame(catalog_table(catalog.get("data") or [], details=details), backend)


def catalog_table(records: Sequence[dict[str, Any]], details: bool = False) -> pa.Table:
    """The catalog's records as the documented table."""
    rows = []
    for record in records:
        r = drop_internal(record)
        aliases = r.get("search_aliases") or {}
        r["search_aliases_en"] = aliases.get("en") or []
        r["search_aliases_es"] = aliases.get("es") or []
        rows.append(r)
    fields = list(COMPACT_FIELDS) + (list(FULL_FIELDS) if details else [])
    list_cols = ("detail_levels", "grain", "year_gaps", "search_aliases_en", "search_aliases_es")
    table = records_to_table(rows, fields=fields, list_cols=list_cols)
    table = apply_schema_types(table, CATALOG_TYPES)
    if "year_gaps" in table.column_names:
        i = table.column_names.index("year_gaps")
        gaps = [[int(y) for y in v] for v in table.column("year_gaps").to_pylist()]
        table = table.set_column(i, "year_gaps", pa.array(gaps, pa.list_(pa.int64())))
    return table


def _check_catalog_filters(main_topic: Any, level: Any, year: Any) -> None:
    """Check the catalog and search filters."""
    if main_topic is not None and not isinstance(main_topic, str):
        raise TypeError("`main_topic` must be a single string, such as 'education'.")
    if level is not None and not isinstance(level, str):
        raise TypeError("`level` must be a single string, such as 'schools'.")
    if year is not None and (
        isinstance(year, bool) or not isinstance(year, (int, float)) or not float(year).is_integer()
    ):
        raise TypeError("`year` must be a single year, such as 2024.")


SEARCH_FIELDS = (
    "name",
    "title",
    "summary",
    "main_topic",
    "detail_levels",
    "year_min",
    "year_max",
    "score",
    "matched_on",
    "matched_columns",
)


@overload
def search(
    query: str,
    main_topic: str | None = ...,
    level: str | None = ...,
    year: int | None = ...,
    n: int = ...,
    *,
    quiet: bool = ...,
    backend: Literal["pandas"],
) -> pd.DataFrame: ...
@overload
def search(
    query: str,
    main_topic: str | None = ...,
    level: str | None = ...,
    year: int | None = ...,
    n: int = ...,
    *,
    quiet: bool = ...,
    backend: Literal["polars"],
) -> pl.DataFrame: ...
@overload
def search(
    query: str,
    main_topic: str | None = ...,
    level: str | None = ...,
    year: int | None = ...,
    n: int = ...,
    *,
    quiet: bool = ...,
    backend: None = ...,
) -> Frame: ...
def search(
    query: str,
    main_topic: str | None = None,
    level: str | None = None,
    year: int | None = None,
    n: int = 20,
    *,
    quiet: bool = False,
    backend: Literal["pandas", "polars"] | None = None,
) -> Frame:
    """Search the catalog.

    Ranked dataset search from plain words, in English or Spanish ("jobless
    rate", "kids missing school", "desempleo"). Use it when you know what
    you are looking for but not what the dataset is called.

    Search is hybrid: keyword matching plus matching by meaning. The query
    text is sent to the Georgia Civic Data API, which embeds it with Voyage
    AI for the meaning half and never logs it. This is the one function
    whose results can't be reproduced by filtering :func:`datasets`
    locally, and the ranking can change between releases of the platform.

    Parameters
    ----------
    query : str
        Plain words.
    main_topic, level, year : optional
        The same filters as :func:`datasets`: a subject area, a detail level
        and a year. Default: no filter.
    n : int, default 20
        The number of matches to return, 1 to 100.
    quiet : bool, default False
        ``True`` silences the notes on the search (see Returns).
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        One row per match, best first, with columns:

        - ``rank``: integer, 1 is the best match.
        - ``name``, ``title``, ``summary``, ``main_topic``: the dataset.
        - ``detail_levels``: list column of the levels it publishes.
        - ``year_min``, ``year_max``: integers, the years covered.
        - ``score``: float, the match score.
        - ``matched_on``: list column of what matched (aliases, columns,
          summary, ...).
        - ``matched_columns``: list column of the dataset's columns that
          matched.

        :func:`meta` on the result gives ``confidence`` (``"high"``,
        ``"medium"`` or ``"low"``), ``retrieval`` (a dict: ``mode`` and
        ``reranked``) and ``total_matches``. On low confidence the function
        advises that nothing in the catalog may fit; it also names any lookup
        tables that matched.

    See Also
    --------
    datasets : the full catalog.
    describe, columns : understand a match.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.search("high school graduation")  # doctest: +SKIP
    >>> gcd.search("desempleo", n=5)  # doctest: +SKIP
    >>> gcd.search("chronic absence", level="districts")  # doctest: +SKIP
    """
    resolve_backend(backend)
    if not isinstance(query, str) or not query.strip():
        raise TypeError("`query` must be a single, non-empty string.")
    _check_catalog_filters(main_topic, level, year)
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 100:
        raise ValueError("`n` must be a whole number from 1 to 100.")
    params: dict[str, list[str]] = {"q": [query], "limit": [str(n)]}
    if main_topic is not None:
        params["main_topic"] = [main_topic]
    if level is not None:
        params["level"] = [level]
    if year is not None:
        params["year"] = [format_number(year)]
    body = get_json("search", params)
    table = search_table(body.get("matches") or [])
    info = {
        "confidence": body.get("confidence"),
        "retrieval": body.get("retrieval"),
        "total_matches": body.get("total_matches"),
    }
    out = to_frame(table, backend, info=info)
    _search_messages(body, quiet)
    return out


def search_table(matches: Sequence[dict[str, Any]]) -> pa.Table:
    """The search matches as the documented table."""
    table = records_to_table(
        [drop_internal(m) for m in matches],
        fields=SEARCH_FIELDS,
        list_cols=("detail_levels", "matched_on", "matched_columns"),
    )
    table = apply_schema_types(
        table,
        {
            "name": "string",
            "title": "string",
            "summary": "string",
            "main_topic": "string",
            "year_min": "integer",
            "year_max": "integer",
            "score": "number",
        },
    )
    return table.add_column(0, "rank", pa.array(range(1, table.num_rows + 1), pa.int64()))


def _search_messages(body: dict[str, Any], quiet: bool) -> None:
    """Confidence, retrieval and lookup-table hints."""
    if is_quiet(quiet):
        return
    if body.get("confidence") == "low":
        advise("Nothing in the catalog may fit this query.")
    mode = (body.get("retrieval") or {}).get("mode")
    if isinstance(mode, str) and mode != "hybrid":
        advise("Search fell back to keywords only, so matches by meaning are missing.")
    tables = [d.get("name") for d in body.get("dimension_matches") or [] if d.get("matched_on")]
    if tables:
        names = ", ".join(repr(t) for t in tables)
        advise(f"Lookup tables that match: {names}. See gcd.dimension().")
