"""Lookup tables: :func:`dimension` and the cached full tables the name
resolver and :func:`locate` read."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, overload

import pandas as pd
import pyarrow as pa

from . import _cache
from ._api import build_url, perform
from ._frames import Frame, records_to_table, to_frame
from ._options import resolve_backend
from ._params import (
    _union,
    as_names,
    check_n_max,
    encode_filters,
    format_number,
)
from ._places import resolve_places
from ._schema import apply_schema_types, check_name_arg, empty_typed, lookup_schema, schema_types

if TYPE_CHECKING:
    import polars as pl


@overload
def dimension(
    name: str,
    *,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    q: str | None = ...,
    columns: str | list[str] | None = ...,
    n_max: int | None = ...,
    backend: Literal["pandas"],
    **filters: Any,
) -> pd.DataFrame: ...
@overload
def dimension(
    name: str,
    *,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    q: str | None = ...,
    columns: str | list[str] | None = ...,
    n_max: int | None = ...,
    backend: Literal["polars"],
    **filters: Any,
) -> pl.DataFrame: ...
@overload
def dimension(
    name: str,
    *,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    q: str | None = ...,
    columns: str | list[str] | None = ...,
    n_max: int | None = ...,
    backend: None = ...,
    **filters: Any,
) -> Frame: ...
def dimension(
    name: str,
    *,
    district: str | list[str] | None = None,
    school: str | list[str] | None = None,
    county: str | list[str] | None = None,
    q: str | None = None,
    columns: str | list[str] | None = None,
    n_max: int | None = None,
    backend: Literal["pandas", "polars"] | None = None,
    **filters: Any,
) -> Frame:
    """Get the rows of a lookup table.

    Returns one of the platform's six lookup tables, the reference lists
    every dataset's codes point to. They hold much more than names, and the
    API never adds it to dataset rows:

    - ``"districts"``: district name, former names, type, Census id, county,
      address, coordinates, active flag.
    - ``"schools"``: school name, former names, level, grade span, county,
      NCES id, address, phone, website, coordinates, locale (city, suburb,
      town, rural), charter and active flags.
    - ``"counties"``: the 159 county names (without "County").
    - ``"tracts"``: 2020 Census tracts with county, land area and population.
    - ``"block_groups"``: 2020 block groups with tract, county, land area,
      population, housing units and households.
    - ``"demographics"``: each demographic group's label and category.

    Use it to analyze results by locale, map schools, or browse what exists
    ("every school in Fulton County"). Unfiltered tables are cached for the
    session.

    **Joining schools.** School codes repeat across districts, so join on
    ``district_code`` **and** ``school_code`` together::

        schools = gcd.dimension(
            "schools", columns=["district_code", "school_code", "locale"]
        )
        grad.merge(schools, on=["district_code", "school_code"], how="left")

    Parameters
    ----------
    name : str
        The lookup table: ``"districts"``, ``"schools"``, ``"counties"``,
        ``"tracts"``, ``"block_groups"`` or ``"demographics"``.
    district, school, county : str or list of str, optional
        Places by name, matched exactly against current and former names
        (ignoring case, accents and a trailing "County") and turned into
        codes. Each applies only to tables with that code column.
    q : str, optional
        Partial text search over the table's name columns, ignoring case and
        accents (``q="eastside"``). Unlike the name arguments, it matches
        part of a name and returns every hit, so it is the tool for browsing.
    columns : str or list of str, optional
        The columns to return. Default: all.
    n_max : int, optional
        The most rows to return. Default ``None``: all.
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option
        (``"pandas"`` unless changed with :func:`set_option`).
    **filters
        Named filters on the table's key, enum and boolean columns, and
        ``county_fips``, ``district_code`` or ``tract_geoid`` where the table
        has them. Each takes a value or a list (values are OR'd; filters are
        AND'd), for example ``active=True``,
        ``district_type="state_charter"`` or ``county_fips="13121"``.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        One row per district, school, county, tract, block group or
        demographic group, ordered by the table's primary key and typed from
        its schema: codes (``district_code``, ``school_code``,
        ``county_fips``, ``tract_geoid``, ``block_group_geoid``,
        ``demographic``) and text columns are strings, coordinates and areas
        floats, counts and ``directory_year`` integers, ``active`` and
        ``charter`` booleans. See :func:`columns` for each table's columns.

    See Also
    --------
    columns : a table's column dictionary.
    rows : results carry these tables' names beside their codes.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.dimension("counties")  # doctest: +SKIP
    >>> gcd.dimension("schools", county="Fulton", active=True)  # doctest: +SKIP
    >>> gcd.dimension("districts", district_type="state_charter")  # doctest: +SKIP
    >>> gcd.dimension(
    ...     "schools", q="eastside",
    ...     columns=["district_code", "school_code", "school_name"],
    ... )  # doctest: +SKIP
    """
    check_name_arg(name, "name")
    resolve_backend(backend)
    if q is not None and (not isinstance(q, str) or not q):
        raise TypeError("`q` must be a single string.")
    columns_list = as_names(columns, "columns")
    limit = check_n_max(n_max)
    encoded = encode_filters(filters)
    schema = lookup_schema(name)
    table_columns = list(schema_types(schema))
    places = resolve_places(
        district,
        school,
        county,
        filters=encoded,
        columns=table_columns,
        target=f'the lookup table "{name}"',
    )

    query = dict(encoded)
    schools = places.schools or []
    district_codes = _union(
        query.get("district_code"), places.district_code, [d for d, _ in schools]
    )
    if district_codes:
        query["district_code"] = district_codes
    county_codes = _union(query.get("county_fips"), places.county_fips)
    if county_codes:
        query["county_fips"] = county_codes
    school_codes = _union(query.get("school_code"), [s for _, s in schools])
    if school_codes:
        query["school_code"] = school_codes
    if q is not None:
        query["q"] = [q]
    request_columns = columns_list
    if columns_list is not None and places.schools is not None:
        request_columns = _union(columns_list, ["district_code", "school_code"])
    if request_columns is not None:
        query["columns"] = request_columns

    if not query:
        table = lookup_table(name)
        if math.isfinite(limit):
            table = table.slice(0, int(limit))
        return to_frame(table, backend)

    page_limit = limit if places.schools is None else math.inf
    table = fetch_dimension_rows(name, query, n_max=page_limit, schema=schema)
    if places.schools is not None:
        wanted = set(places.schools)
        keep = [
            (d, s) in wanted
            for d, s in zip(
                table.column("district_code").to_pylist(), table.column("school_code").to_pylist()
            )
        ]
        table = table.filter(pa.array(keep, pa.bool_()))
        if columns_list is not None:
            table = table.select([c for c in columns_list if c in table.column_names])
        if math.isfinite(limit):
            table = table.slice(0, int(limit))
    return to_frame(table, backend)


def lookup_table(name: str) -> pa.Table:
    """Every row of a lookup table, typed, cached for the session."""
    return _cache.cache_get_or_set(
        f"lookup:{name}",
        lambda: fetch_dimension_rows(name, {}, schema=lookup_schema(name)),
    )


def fetch_dimension_rows(
    name: str,
    query: Mapping[str, list[str]],
    n_max: float = math.inf,
    schema: Mapping[str, Any] | None = None,
) -> pa.Table:
    """Page through ``GET /dimensions/{name}/rows``."""
    types = schema_types(schema or {})
    pages: list[pa.Table] = []
    got = 0
    while True:
        page_query = dict(query)
        page_query["limit"] = [format_number(min(n_max - got, 10000))]
        if got > 0:
            page_query["offset"] = [format_number(got)]
        body = perform("GET", build_url(["dimensions", name, "rows"], page_query)).json()
        data = body.get("data") or []
        if data:
            pages.append(apply_schema_types(records_to_table(data), types))
        got += len(data)
        pagination = body.get("pagination") or {}
        if not pagination.get("has_more") or got >= n_max or not data:
            break
    if not pages:
        return empty_typed(list(query.get("columns") or types), types)
    if len(pages) == 1:
        return pages[0]
    return pa.concat_tables(pages, promote_options="permissive")
