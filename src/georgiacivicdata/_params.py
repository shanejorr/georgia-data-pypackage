"""Building query parameters: years, list filters, missing-value and boolean
encoding, school ids, and the switch to POST for very long filter lists.

Every query value is a list of strings; single-valued parameters are lists
of one.
"""

from __future__ import annotations

import datetime as dt
import itertools
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ._api import build_url

NULL_TOKEN = "__null__"
"""The token the API reads as "this column is NULL"."""

MAX_URL_CHARS = 6000
"""URLs longer than this go as ``POST /datasets/{name}/query``."""

RESERVED_PARAMS = ("limit", "offset", "format", "fields", "verbosity", "source")
"""Parameters the fetch strategy owns; refused as filters."""


def is_missing(v: Any) -> bool:
    """None, NaN, pandas NA/NaT."""
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    try:
        import pandas as pd

        if v is pd.NA or v is pd.NaT:
            return True
    except ImportError:  # pragma: no cover
        pass
    return type(v).__name__ in ("NaTType", "NAType")


def as_values(x: Any) -> list[Any]:
    """A scalar or a collection (list, tuple, set, range, array, Series) as a list."""
    if isinstance(x, (str, bytes)) or not isinstance(x, Iterable):
        return [x]
    if isinstance(x, Mapping):
        raise TypeError("must be a value or a list of values, not a dict")
    if hasattr(x, "to_list"):
        return list(x.to_list())
    if hasattr(x, "tolist"):
        out = x.tolist()
        return list(out) if isinstance(out, list) else [out]
    return list(x)


def format_number(x: float | int) -> str:
    """A number as plain decimal text (never scientific notation)."""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    x = float(x)
    if x.is_integer() and abs(x) < 1e15:
        return str(int(x))
    out = f"{x:.15f}".rstrip("0").rstrip(".")
    return out if out not in ("", "-") else "0"


def encode_value(v: Any, arg: str) -> str:
    """One filter value as the API's text."""
    if is_missing(v):
        return NULL_TOKEN
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        v = v.item()  # numpy scalars
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return format_number(v)
    if isinstance(v, dt.datetime):
        return v.date().isoformat() if v.time() == dt.time() else v.isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str):
        return v
    raise TypeError(
        f"Filter `{arg}` must be strings, numbers, booleans or dates, not {type(v).__name__}."
    )


def encode_values(x: Any, arg: str) -> list[str]:
    """Encode one filter: ``None``/``NaN`` in a list becomes ``__null__``,
    booleans ``true``/``false``, numbers plain decimal text, dates ISO 8601.
    Duplicates are dropped, order kept."""
    try:
        values = as_values(x)
    except TypeError as exc:
        raise TypeError(f"Filter `{arg}` {exc}.") from None
    out: list[str] = []
    for v in values:
        if isinstance(v, (list, tuple, dict, set)):
            raise TypeError(f"Filter `{arg}` must be a value or a flat list of values.")
        text = encode_value(v, arg)
        if text not in out:
            out.append(text)
    return out


def encode_years(year: Any) -> dict[str, list[str]]:
    """Encode the ``year`` argument.

    One year, or a run of consecutive years, becomes ``year`` / ``year_min``
    + ``year_max``; anything else an exact list.
    """
    if year is None:
        return {}
    message = (
        "`year` must be a whole year or a list of whole years, such as 2024 or range(2019, 2025)."
    )
    try:
        values = as_values(year)
    except TypeError:
        raise TypeError(message) from None
    years: list[int] = []
    for v in values:
        if hasattr(v, "item") and not isinstance(v, (str, bytes)):
            v = v.item()
        if isinstance(v, bool) or not isinstance(v, (int, float)) or is_missing(v):
            raise TypeError(message)
        if not float(v).is_integer():
            raise ValueError(message)
        years.append(int(v))
    if not years:
        raise ValueError(message)
    years = sorted(set(years))
    if len(years) == 1:
        return {"year": [str(years[0])]}
    if all(b - a == 1 for a, b in itertools.pairwise(years)):
        return {"year_min": [str(years[0])], "year_max": [str(years[-1])]}
    return {"year": [str(y) for y in years]}


def encode_filters(filters: Mapping[str, Any]) -> dict[str, list[str]]:
    """Encode the named filters given as keyword arguments.

    ``None`` filters are dropped; ``school_id`` becomes the API's ``school``
    pair filter.
    """
    bad = [name for name in filters if name in RESERVED_PARAMS]
    if bad:
        raise ValueError(
            f"`{bad[0]}` can't be given as a filter: the package chooses the page "
            "size and format; use `n_max` to cap rows."
        )
    if "school" in filters:
        raise ValueError(
            "Use `school_id` for schools as 'DISTRICT-SCHOOL' codes; `school` takes school names."
        )
    out: dict[str, list[str]] = {}
    for name, x in filters.items():
        if x is None:
            continue
        values = encode_values(x, name)
        if not values:
            raise ValueError(f"Filter `{name}` is empty; give at least one value or leave it out.")
        out["school" if name == "school_id" else name] = values
    return out


@dataclass
class Places:
    """Resolved places: codes and (district, school) pairs."""

    district_code: list[str] | None = None
    county_fips: list[str] | None = None
    school_pairs: list[str] | None = None
    schools: list[tuple[str, str]] | None = None


def _union(*parts: list[str] | None) -> list[str]:
    out: list[str] = []
    for part in parts:
        for v in part or []:
            if v not in out:
                out.append(v)
    return out


def dataset_query(
    filters: Mapping[str, list[str]],
    years: Mapping[str, list[str]],
    detail: str | None,
    places: Places,
    columns: list[str] | None = None,
    sort: list[str] | None = None,
) -> dict[str, list[str]]:
    """Combine the query for a dataset route (rows, values)."""
    query: dict[str, list[str]] = dict(years)
    if detail is not None:
        query["detail"] = [detail]
    query.update(filters)
    if places.district_code:
        query["district_code"] = _union(query.get("district_code"), places.district_code)
    if places.county_fips:
        query["county_fips"] = _union(query.get("county_fips"), places.county_fips)
    if places.school_pairs:
        query["school"] = _union(query.get("school"), places.school_pairs)
    if columns is not None:
        query["columns"] = list(columns)
    if sort is not None:
        query["sort"] = list(sort)
    return query


@dataclass
class RequestSpec:
    """A request to send: method, URL and (for POST) the JSON body."""

    method: str
    url: str
    json_body: Any = None


def dataset_request(name: str, route: str, query: Mapping[str, list[str]]) -> RequestSpec:
    """A request for a dataset route, switching to ``POST /query`` when the
    URL would be too long. Only the rows route has a POST twin."""
    url = build_url(["datasets", name, route], query)
    if route == "rows" and len(url) > MAX_URL_CHARS:
        body = {k: list(v) for k, v in query.items()}
        return RequestSpec("POST", build_url(["datasets", name, "query"]), body)
    return RequestSpec("GET", url)


def as_names(x: Any, arg: str, allow_none: bool = True) -> list[str] | None:
    """An optional list of non-empty strings (a single string is a list of one)."""
    if x is None and allow_none:
        return None
    message = f"`{arg}` must be a string or a list of non-empty strings."
    try:
        values = as_values(x)
    except TypeError:
        raise TypeError(message) from None
    if not values or not all(isinstance(v, str) and v for v in values):
        raise TypeError(message)
    return [str(v) for v in values]


def check_query_args(
    detail: Any, columns: Any, sort: Any
) -> tuple[list[str] | None, list[str] | None]:
    """Check ``detail``, ``columns`` and ``sort``; return the last two as lists."""
    if detail is not None and (not isinstance(detail, str) or not detail):
        raise ValueError(
            "`detail` must be one detail level, such as 'districts'. To combine "
            "levels, call once per level and concatenate the rows."
        )
    return as_names(columns, "columns"), as_names(sort, "sort")


def check_flag(x: Any, arg: str) -> bool:
    """A single True or False."""
    if not isinstance(x, bool):
        raise TypeError(f"`{arg}` must be True or False.")
    return x


def check_n_max(x: Any) -> float:
    """``n_max``: None (all) or a whole number of at least 1."""
    if x is None:
        return math.inf
    if isinstance(x, bool) or not isinstance(x, (int, float)) or math.isnan(x) or x < 1:
        raise ValueError("`n_max` must be None or a whole number of at least 1.")
    return float(x)
