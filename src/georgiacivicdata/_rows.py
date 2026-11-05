"""Get data: :func:`rows`."""

from __future__ import annotations

import csv
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, overload

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv

from ._api import build_url, perform
from ._frames import Frame, records_to_table, to_frame
from ._messages import advise, inform
from ._options import get_option, is_quiet, resolve_backend
from ._params import (
    check_flag,
    check_n_max,
    check_query_args,
    dataset_query,
    dataset_request,
    encode_filters,
    encode_years,
    format_number,
)
from ._places import resolve_places
from ._schema import (
    apply_schema_types,
    code_columns,
    drop_empty_codes,
    drop_internal,
    empty_typed,
    relocate_labels,
    row_types,
    schema_types,
    select,
    table_schema,
)

if TYPE_CHECKING:
    import polars as pl

PAGE_MAX = 10000


@overload
def rows(
    name: str,
    *,
    year: int | Sequence[int] | None = ...,
    detail: str | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    labels: bool = ...,
    columns: str | list[str] | None = ...,
    sort: str | list[str] | None = ...,
    n_max: int | None = ...,
    cache: bool | None = ...,
    quiet: bool = ...,
    backend: Literal["pandas"],
    **filters: Any,
) -> pd.DataFrame: ...
@overload
def rows(
    name: str,
    *,
    year: int | Sequence[int] | None = ...,
    detail: str | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    labels: bool = ...,
    columns: str | list[str] | None = ...,
    sort: str | list[str] | None = ...,
    n_max: int | None = ...,
    cache: bool | None = ...,
    quiet: bool = ...,
    backend: Literal["polars"],
    **filters: Any,
) -> pl.DataFrame: ...
@overload
def rows(
    name: str,
    *,
    year: int | Sequence[int] | None = ...,
    detail: str | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    labels: bool = ...,
    columns: str | list[str] | None = ...,
    sort: str | list[str] | None = ...,
    n_max: int | None = ...,
    cache: bool | None = ...,
    quiet: bool = ...,
    backend: None = ...,
    **filters: Any,
) -> Frame: ...
def rows(
    name: str,
    *,
    year: int | Sequence[int] | None = None,
    detail: str | None = None,
    district: str | list[str] | None = None,
    school: str | list[str] | None = None,
    county: str | list[str] | None = None,
    labels: bool = True,
    columns: str | list[str] | None = None,
    sort: str | list[str] | None = None,
    n_max: int | None = None,
    cache: bool | None = None,
    quiet: bool = False,
    backend: Literal["pandas", "polars"] | None = None,
    **filters: Any,
) -> Frame:
    """Get rows of a dataset.

    The core function: the rows of one dataset at one detail level, as a
    data frame typed from the dataset's schema, with place names beside
    their codes.

    **It returns every category and group the filters don't exclude.**
    Nothing is pinned by default: no single demographic group, no single
    subject. A call with only a dataset name returns the whole dataset at its
    default detail level.

    **Filters.** Give filters as keyword arguments; each value is one value
    or a list. Values within one filter are OR'd; different filters are
    AND'd. Accepted names:

    - any categorical column: ``subject="mathematics"``,
      ``demographic=["all", "black"]``;
    - geography codes: ``district_code``, ``school_code``, ``county_fips``,
      ``tract_geoid``, ``block_group_geoid``;
    - ``school_id``: schools as ``"DISTRICT-SCHOOL"`` codes
      (``school_id=["761-0199", "660-0104"]``), the form :func:`locate`
      returns (a school code alone is not unique across districts);
    - lookup-table attributes: ``district_type="state_charter"``,
      ``school_level="high"``, ``locale="rural"``,
      ``demographic_category="race"``;
    - metric bounds: ``graduation_rate_min=0.9``, ``num_cohort_max=50``
      (inclusive, in stored units).

    ``None`` inside a list selects rows where a nullable column is empty
    (``assessment_type=[None]``); a filter that is ``None`` itself is
    ignored. Booleans become ``true`` / ``false``. The API validates every
    filter and its errors name what went wrong; :func:`describe` lists each
    dataset's filters and their values.

    **Labels.** With ``labels=True`` (the default) the rows carry the API's
    joined name columns, each right after its code: ``district_name``,
    ``district_census_id`` and ``district_type`` after ``district_code``;
    ``school_name`` after ``school_code``; ``county_name``, ``tract_name``
    and ``block_group_name`` after their codes; ``demographic_label`` and
    ``demographic_category`` after ``demographic``. Codes are always kept:
    school names repeat across districts, names change over time, and joins
    run on codes. Categorical values (``subject``, ``grade_cluster``) are
    readable snake_case codes already. Other lookup-table attributes (school
    addresses, locale, coordinates) are not joined; get them from
    :func:`dimension` and merge. ``labels=False`` asks for the dataset's own
    columns only, for large pulls. Either way, code columns that would be
    empty on every row (a district row's ``school_code``, a state row's
    geography codes) are left out, so both settings give the same shape.

    **Missing values and totals.** A missing metric usually means the value
    was **suppressed** to protect privacy (small counts), **not zero**; the
    schema's ``null_semantics`` says which (:func:`describe`). Because
    nothing is pinned, results hold the ``all`` totals beside the subgroups:
    never add a total to its subgroups. The API's advisories say so when
    they apply, as :class:`GCDAdvisory` warnings (``quiet=True`` or
    ``set_option("quiet", True)`` silences them; they stay in
    ``meta(df)["advisories"]``). Rates must be pooled from their counts,
    never averaged: ``sum(num_graduates) / sum(num_cohort)``, not
    ``mean(graduation_rate)``. :func:`columns` shows each metric's
    numerator and denominator.

    **Large downloads and the disk cache.** Up to 10,000 rows come back as
    one JSON page. A larger result is downloaded in full as CSV in one
    response; the metadata and advisories then come from the first JSON page
    and describe its first 10,000 rows. With ``cache=True`` (or
    ``set_option("cache", True)``), responses are kept in the user cache
    folder with their ``ETag``. Repeating a request asks the server whether
    the data changed: an unchanged answer reuses the saved copy without
    downloading, and a new data release downloads afresh. A response the
    server marks fresh (for five minutes) is reused without asking. Clear it
    with :func:`cache_clear`.

    **Data license.** The data is CC BY 4.0: credit Georgia Civic Data and
    the original source, as :func:`citation` writes.

    Parameters
    ----------
    name : str
        The dataset's name, such as ``"graduation_rate_4_year_cohort"`` (see
        :func:`datasets` and :func:`search`).
    year : int or list of int, optional
        Years to keep. A run of consecutive years (``range(2019, 2025)``) is
        sent as a range; anything else (``[2019, 2024]``) as exact years.
        Default: all years.
    detail : str, optional
        The one level the rows describe, such as ``"schools"``,
        ``"districts"``, ``"states"``, ``"counties"`` or ``"tracts"``.
        Default: the dataset's default (the finest level, except Census
        datasets, which default to counties). To combine levels, call once
        per level and concatenate.
    district, school, county : str or list of str, optional
        Places by name, such as ``district="Fulton County"``,
        ``school="Roswell High School"``, ``county=["Fulton", "DeKalb"]``.
        Matched exactly against current and former names (ignoring case,
        accents and a trailing "County"); an unknown or ambiguous name is an
        error that lists suggestions or candidates. A school name found in
        more than one district needs ``district`` too. For any one place,
        give its code or its name, not both.
    labels : bool, default True
        ``True`` adds place names beside codes; ``False`` returns codes only.
    columns : str or list of str, optional
        Return only these columns. Default: all.
    sort : str or list of str, optional
        Columns to sort by on the server; prefix ``-`` for descending
        (``"-graduation_rate"``). Missing values sort last. Mostly useful
        with ``n_max`` for a top N. Default: the dataset's own order (its
        grain).
    n_max : int, optional
        The most rows to return. Default ``None``: all.
    cache : bool, optional
        ``True`` to use the disk cache. Default: the ``cache`` option
        (``False``).
    quiet : bool, default False
        ``True`` silences the advisories.
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option
        (``"pandas"``).
    **filters
        Named filters (see "Filters" above).

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        Rows at one detail level, typed from the schema: codes and names are
        strings (leading zeros kept), ``year`` and counts integers, rates and
        proportions floats (proportions on the 0-1 scale), booleans boolean.
        In pandas, integers are ``Int64``, booleans ``boolean`` and text
        ``string`` (nullable dtypes); floats are ``float64``. Columns come in
        grain order: ``year``, each geography code followed by its names,
        ``demographic`` and its labels, other categorical columns, then
        metrics. :func:`columns` describes each column. :func:`meta` returns
        the response's metadata: dataset, title, detail, key metric, units,
        ``null_semantics``, source, citation, license, advisories, data
        version, ``updated_at`` and the request URL.

    See Also
    --------
    values : which category values exist under a filter.
    describe, columns : understand a dataset.
    citation : cite it.

    Examples
    --------
    >>> import georgiacivicdata as gcd

    Names and codes (the default), one district by name:

    >>> grad = gcd.rows(
    ...     "graduation_rate_4_year_cohort",
    ...     district="Fulton County",
    ...     demographic=["all", "black", "hispanic"],
    ...     year=range(2020, 2025),
    ... )  # doctest: +SKIP

    One school, by name within its district:

    >>> gcd.rows(
    ...     "graduation_rate_4_year_cohort",
    ...     district="Fulton County", school="Roswell High School",
    ...     demographic="all",
    ... )  # doctest: +SKIP

    Statewide schools, one subject, codes only, as Polars:

    >>> gcd.rows(
    ...     "ccrpi_content_mastery", year=2025, detail="schools",
    ...     grade_cluster="high", subject="mathematics", labels=False,
    ...     backend="polars",
    ... )  # doctest: +SKIP

    Top 10 counties by unemployment:

    >>> gcd.rows("employment", year=2024, sort="-unemployment_rate", n_max=10)  # doctest: +SKIP
    """
    from ._schema import check_name_arg

    check_name_arg(name, "name")
    check_flag(labels, "labels")
    resolve_backend(backend)
    use_cache = get_option("cache") if cache is None else check_flag(cache, "cache")
    check_flag(quiet, "quiet")
    limit = check_n_max(n_max)
    columns_list, sort_list = check_query_args(detail, columns, sort)
    encoded = encode_filters(filters)
    years = encode_years(year)
    schema = table_schema(name, "rows")
    own_columns = list(schema_types(schema))
    places = resolve_places(
        district,
        school,
        county,
        filters=encoded,
        columns=own_columns,
        target=f'the dataset "{name}"',
    )
    request_columns = (
        columns_list if columns_list is not None else (None if labels else own_columns)
    )
    query = dataset_query(encoded, years, detail, places, request_columns, sort_list)

    silent = is_quiet(quiet)
    data, meta_block, url = _fetch_rows(
        name, query, n_max=limit, cache=bool(use_cache), quiet=silent
    )
    table = shape_rows(
        data,
        schema,
        labels=labels,
        columns=columns_list,
        omitted=(meta_block or {}).get("omitted_columns"),
    )
    info = rows_meta(meta_block, url)
    out = to_frame(table, backend, info=info)
    if not silent:
        for advisory in info["advisories"]:
            advise(str(advisory.get("message")))
    return out


def _fetch_rows(
    name: str,
    query: Mapping[str, list[str]],
    n_max: float = math.inf,
    cache: bool = False,
    quiet: bool = False,
) -> tuple[Any, dict[str, Any] | None, str]:
    """Fetch rows: one JSON page, or the whole result as CSV when it is larger.

    Returns the data (JSON records or an Arrow table read from CSV), the
    response's ``meta`` and the request URL.
    """
    limit = min(n_max, PAGE_MAX)
    page_query = {**query, "limit": [format_number(limit)]}
    spec = dataset_request(name, "rows", page_query)
    url = build_url(["datasets", name, "rows"], page_query)
    body = perform(spec.method, spec.url, json_body=spec.json_body, cache=cache).json()
    data: Any = body.get("data") or []
    meta_block = body.get("meta")
    pagination = body.get("pagination") or {}
    if not pagination.get("has_more") or n_max <= limit:
        return data, meta_block, url
    total = pagination.get("total")
    if not quiet and isinstance(total, int):
        n = min(total, n_max) if math.isfinite(n_max) else total
        if n < total:
            inform(f"Downloading {total:,} rows as CSV (keeping the first {int(n):,}).")
        else:
            inform(f"Downloading {total:,} rows as CSV.")
    csv_spec = dataset_request(name, "rows", {**query, "format": ["csv"]})
    table = _download_csv(csv_spec.method, csv_spec.url, csv_spec.json_body, cache=cache)
    if math.isfinite(n_max):
        table = table.slice(0, int(n_max))
    return table, meta_block, url


def _download_csv(method: str, url: str, json_body: Any, cache: bool = False) -> pa.Table:
    """Stream a CSV response to a temporary file and read every column as text."""
    handle, tmp = tempfile.mkstemp(suffix=".csv")
    os.close(handle)
    path = Path(tmp)
    try:
        perform(method, url, json_body=json_body, timeout=900, cache=cache, stream_to=path)
        return read_csv_text(path)
    finally:
        path.unlink(missing_ok=True)


def read_csv_text(path: Path) -> pa.Table:
    """Read a CSV file with every column as text (empty fields are null)."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh), [])
    if not header:
        return pa.table({})
    return pacsv.read_csv(
        path,
        convert_options=pacsv.ConvertOptions(
            column_types={c: pa.string() for c in header},
            null_values=[""],
            strings_can_be_null=True,
            quoted_strings_can_be_null=True,
        ),
    )


def shape_rows(
    data: Any,
    schema: Mapping[str, Any],
    labels: bool = True,
    columns: list[str] | None = None,
    omitted: Sequence[str] | None = None,
) -> pa.Table:
    """Type, order and trim the rows."""
    types = row_types(schema)
    if isinstance(data, pa.Table):
        table = data
    elif data:
        table = records_to_table(data)
    else:
        table = None
    if table is None or table.num_rows == 0:
        expected = (
            columns
            if columns is not None
            else (list(types) if labels else list(schema_types(schema)))
        )
        skip = set(omitted or [])
        table = empty_typed([c for c in expected if c not in skip], types)
    table = apply_schema_types(table, types)
    table = select(table, relocate_labels(table.column_names, schema.get("foreign_keys") or []))
    if not labels and columns is None:
        table = drop_empty_codes(table, code_columns(schema))
    return table


def rows_meta(meta: Mapping[str, Any] | None, url: str) -> dict[str, Any]:
    """The metadata of a result: the response's ``meta`` without its internal
    key, advisories as a list of ``{code, message}`` dicts, plus the request
    URL."""
    info: dict[str, Any] = drop_internal(dict(meta or {}))
    advisories = info.get("advisories")
    info["advisories"] = [
        {"code": a.get("code"), "message": a.get("message")}
        for a in (advisories if isinstance(advisories, list) else [])
        if isinstance(a, dict)
    ]
    info["request_url"] = url
    return info
