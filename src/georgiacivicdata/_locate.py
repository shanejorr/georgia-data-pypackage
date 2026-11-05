"""Locate points or addresses: :func:`locate`."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, overload

import pandas as pd
import pyarrow as pa

from . import _cache
from ._api import build_url, perform
from ._errors import gcd_error
from ._frames import Frame, make_array, to_frame
from ._messages import advise
from ._options import is_quiet, resolve_backend
from ._params import as_values, is_missing
from ._zones import GRADE_CODES, ZONE_LEVELS, check_year1, normalize_grade

if TYPE_CHECKING:
    import polars as pl

BATCH_SIZE = 1000
"""Points per ``POST /locate`` request (the API's maximum)."""


@overload
def locate(
    lat: Any = ...,
    lon: Any = ...,
    address: Any = ...,
    id: Any = ...,
    grade: str | int | None = ...,
    year: int | None = ...,
    *,
    quiet: bool = ...,
    backend: Literal["pandas"],
) -> pd.DataFrame: ...
@overload
def locate(
    lat: Any = ...,
    lon: Any = ...,
    address: Any = ...,
    id: Any = ...,
    grade: str | int | None = ...,
    year: int | None = ...,
    *,
    quiet: bool = ...,
    backend: Literal["polars"],
) -> pl.DataFrame: ...
@overload
def locate(
    lat: Any = ...,
    lon: Any = ...,
    address: Any = ...,
    id: Any = ...,
    grade: str | int | None = ...,
    year: int | None = ...,
    *,
    quiet: bool = ...,
    backend: None = ...,
) -> Frame: ...
def locate(
    lat: Any = None,
    lon: Any = None,
    address: Any = None,
    id: Any = None,
    grade: str | int | None = None,
    year: int | None = None,
    *,
    quiet: bool = False,
    backend: Literal["pandas", "polars"] | None = None,
) -> Frame:
    """Locate points or addresses.

    The county, 2020 Census tract and block group, school district and zoned
    schools that points or street addresses fall in.

    Points are sent to the API's ``POST /locate`` route in batches of up to
    1,000, so coordinates never appear in URLs and nothing is cached.
    **Addresses never reach the Georgia Civic Data API**: the package
    geocodes them on your computer with the U.S. Census batch geocoder
    (https://geocoding.geo.census.gov/geocoder/, benchmark
    ``Public_AR_Current``, the address data the API's own search uses; up to
    10,000 addresses per upload), then sends the coordinates as points. An
    address the Census can't match is never sent. To geocode with another
    service, geocode first and pass ``lat`` and ``lon``.

    A zone is the default assignment, not the only option: a student may
    attend another public school by transfer, or a charter, magnet or other
    choice school. This is not an official enrollment determination; confirm
    with the school district.

    **Output.** A long data frame: **for each input, one row per place it
    falls in.** A typical location gives seven rows: its county, tract, block
    group and school district, then one row per zoned school. Rows for each
    input come in a fixed order: county, tract, block group, district, then
    elementary, middle and high schools by grade.

    A level can have more than one school row: some homes are zoned to one
    elementary school for kindergarten to grade 2 and another for grades
    3-5. The ``grades`` column tells them apart; pass ``grade`` to keep only
    the school for one grade.

    The ``note`` column is missing normally, and one plain sentence
    otherwise, so a missing row is never silent:

    - a level with no zone collected yet, a gap between zones, or a level
      served by another district gets a row with missing id, name and
      grades, and a note saying why;
    - an input outside Georgia, a point the API rejects, or an address the
      Census can't match gets one row with missing geographic columns and
      the reason; one bad input never stops the batch;
    - in a Department of Defense district the district row has a missing id
      and a note;
    - school rows whose zone has a known pending change, or which overlap
      another school's zone, say so.

    Parameters
    ----------
    lat, lon : float or sequence of float, optional
        Latitude and longitude in decimal degrees (WGS 84), of equal length.
    address : str, sequence of str, or DataFrame, optional
        Street addresses: one-line addresses
        (``"206 Washington St SW, Atlanta, GA 30334"``), or a data frame
        (pandas or Polars) or dict with columns ``street``, ``city``,
        ``state`` and ``zip``. Give either ``lat`` and ``lon`` or
        ``address``, not both.
    id : sequence, optional
        Identifiers for the inputs, the same length, carried into the output
        so results join back to your data. Default: each input's position,
        starting at 0.
    grade : str or int, optional
        Keep only school zones serving this grade (``"pk"``, ``"k"``,
        ``"01"`` to ``"12"``; ``"5"``, ``5`` and ``"K"`` are accepted).
        Default: every grade.
    year : int, optional
        The zones' school year as its ending year (2027 is 2026-27).
        Default: the current zones.
    quiet : bool, default False
        ``True`` silences the once-per-session note on the default
        assignment.
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        Columns, in order:

        1. ``id``.
        2. The input: ``lat``, ``lon`` for points; for addresses
           ``address``, the geocoder's ``match_status`` (``"match"``,
           ``"no_match"``, ``"tie"``), ``match_type`` (``"exact"``,
           ``"non_exact"``), ``matched_address``, and the geocoded ``lat``
           and ``lon``.
        3. ``geographic_type``: ``"county"``, ``"tract"``, ``"block_group"``,
           ``"school_district"``, ``"elementary_school"``,
           ``"middle_school"`` or ``"high_school"``.
        4. ``geographic_id``: county FIPS (``"13121"``), tract GEOID
           (``"13121003500"``), block group GEOID (``"131210035001"``),
           district code (``"761"``), or for a school ``"DISTRICT-SCHOOL"``
           (``"761-4560"``), the form :func:`rows` takes as ``school_id``.
        5. ``geographic_name``: the place's name.
        6. ``grades``: a school row's grade range (``"K-5"``, ``"6-8"``,
           ``"9-12"``); missing on other rows.
        7. ``note``: missing, or why a row is missing or needs care.

        :func:`meta` on the result gives the API's ``assignment_note`` and
        ``note`` on reading the zones.

    See Also
    --------
    school_zones : the zones' shapes and precision (``method``,
        ``accuracy_class``).
    rows : with ``school_id``, data on a located school.

    Examples
    --------
    >>> import georgiacivicdata as gcd

    The Georgia State Capitol, by coordinates and by address:

    >>> gcd.locate(lat=33.7490, lon=-84.3880)  # doctest: +SKIP
    >>> gcd.locate(address="206 Washington St SW, Atlanta, GA 30334")  # doctest: +SKIP

    Only the school for one grade:

    >>> gcd.locate(lat=33.7490, lon=-84.3880, grade=9)  # doctest: +SKIP
    """
    from ._geocode import address_input, census_geocode

    resolve_backend(backend)
    g = normalize_grade(grade)
    y = check_year1(year)
    has_points = lat is not None or lon is not None
    if has_points and address is not None:
        raise ValueError("Give `lat` and `lon`, or `address`, not both.")
    if not has_points and address is None:
        raise ValueError("Give `lat` and `lon`, or `address`.")

    if has_points:
        lats, lons = _check_points(lat, lon)
        input_cols: dict[str, list[Any]] = {"lat": lats, "lon": lons}
        notes = [
            "No coordinates were given." if a is None or b is None else None
            for a, b in zip(lats, lons)
        ]
    else:
        addresses = address_input(address)
        geo = census_geocode(addresses)
        input_cols = {
            "address": addresses.address,
            "match_status": [r.match_status for r in geo],
            "match_type": [r.match_type for r in geo],
            "matched_address": [r.matched_address for r in geo],
            "lat": [r.lat for r in geo],
            "lon": [r.lon for r in geo],
        }
        notes = geocode_notes([r.match_status for r in geo])
    n = len(input_cols["lat"])
    ids = _check_ids(id, n)

    send = [
        i for i in range(n) if input_cols["lat"][i] is not None and input_cols["lon"][i] is not None
    ]
    results: list[dict[str, Any] | None] = [None] * n
    if send:
        found = locate_points(
            [input_cols["lat"][i] for i in send],
            [input_cols["lon"][i] for i in send],
            grade=g,
            year=y,
        )
        for i, r in zip(send, found):
            results[i] = r
    lookups = locate_lookups(results)

    out_rows: list[dict[str, Any]] = []
    for i in range(n):
        result = results[i]
        place_rows = [failure_row(notes[i])] if result is None else locate_rows(result, lookups)
        for row in place_rows:
            record: dict[str, Any] = {"id": ids[i]}
            for name, col in input_cols.items():
                record[name] = col[i]
            record.update(row)
            out_rows.append(record)

    first = next((r for r in results if r is not None and r.get("error") is None), None)
    assignment_note = first.get("assignment_note") if first else None
    info = {"assignment_note": assignment_note, "note": first.get("note") if first else None}
    names = [
        "id",
        *input_cols,
        "geographic_type",
        "geographic_id",
        "geographic_name",
        "grades",
        "note",
    ]
    arrays = []
    for name in names:
        values = [r.get(name) for r in out_rows]
        if name in ("lat", "lon"):
            arrays.append(pa.array(values, pa.float64()))
        elif name == "id":
            arrays.append(make_array(values))
        else:
            arrays.append(pa.array(values, pa.string()))
    table = pa.table(arrays, names=names)
    out = to_frame(table, backend, info=info)
    if (
        isinstance(assignment_note, str)
        and not is_quiet(quiet)
        and _cache.first_time("assignment_note")
    ):
        advise(assignment_note)
    return out


def _floats(x: Any, arg: str) -> list[float | None]:
    message = "`lat` and `lon` must be numbers or sequences of numbers of the same length."
    try:
        values = as_values(x)
    except TypeError:
        raise TypeError(message) from None
    out: list[float | None] = []
    for v in values:
        if hasattr(v, "item") and not isinstance(v, (str, bytes)):
            v = v.item()
        if is_missing(v):
            out.append(None)
        elif isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TypeError(message)
        else:
            out.append(float(v))
    return out


def _check_points(lat: Any, lon: Any) -> tuple[list[float | None], list[float | None]]:
    if lat is None or lon is None:
        raise ValueError("Give both `lat` and `lon`.")
    lats, lons = _floats(lat, "lat"), _floats(lon, "lon")
    if not lats or len(lats) != len(lons):
        raise ValueError(
            "`lat` and `lon` must be numbers or sequences of numbers of the same length."
        )
    return lats, lons


def _check_ids(id: Any, n: int) -> list[Any]:
    if id is None:
        return list(range(n))
    try:
        values = as_values(id)
    except TypeError:
        values = []
    if len(values) != n:
        raise ValueError(f"`id` must have one value per input ({n}).")
    return [
        v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v for v in values
    ]


def geocode_notes(statuses: Sequence[str | None]) -> list[str | None]:
    """Notes for addresses the geocoder didn't place."""
    out: list[str | None] = []
    for s in statuses:
        if s is None:
            out.append("No address was given.")
        elif s == "no_match":
            out.append("The U.S. Census geocoder found no match for this address.")
        elif s == "tie":
            out.append(
                "The U.S. Census geocoder found more than one possible match for this address."
            )
        else:
            out.append(None)
    return out


def locate_points(
    lat: Sequence[float | None],
    lon: Sequence[float | None],
    grade: str | None = None,
    year: str | None = None,
    batch_size: int = BATCH_SIZE,
) -> list[dict[str, Any]]:
    """POST points to ``/locate`` in batches, checking the echoed ids.

    The ids sent are the points' positions; the user's own ids never leave
    the computer.
    """
    out: list[dict[str, Any]] = []
    for start in range(0, len(lat), batch_size):
        batch = list(range(start, min(start + batch_size, len(lat))))
        points = [{"id": str(i + 1), "lat": lat[i], "lon": lon[i]} for i in batch]
        body: dict[str, Any] = {"points": points}
        if grade is not None:
            body["grade"] = grade
        if year is not None:
            body["year"] = int(year)
        results = (
            perform("POST", build_url("locate"), json_body=body, timeout=600).json().get("results")
            or []
        )
        echoed = [str(r.get("id")) if r.get("id") is not None else None for r in results]
        if echoed != [str(i + 1) for i in batch]:
            raise gcd_error(
                "The API's location results didn't match the points sent.", code="locate_mismatch"
            )
        out.extend(results)
    return out


def locate_lookups(results: Sequence[dict[str, Any] | None]) -> dict[str, dict[str, str]]:
    """The lookup tables needed to name the counties, tracts and block groups
    found (read whole and locally, so no location leaves the API call)."""
    from ._dimension import lookup_table

    ok = [
        r
        for r in results
        if r is not None
        and r.get("error") is None
        and r.get("coverage_status") != "outside_georgia"
    ]
    if not ok:
        return {}
    out: dict[str, dict[str, str]] = {}
    for field, table, key, name in (
        ("county_fips", "counties", "county_fips", "county_name"),
        ("tract_geoid", "tracts", "tract_geoid", "tract_name"),
        ("block_group_geoid", "block_groups", "block_group_geoid", "block_group_name"),
    ):
        if any(r.get(field) is not None for r in ok):
            t = lookup_table(table)
            out[table] = dict(zip(t.column(key).to_pylist(), t.column(name).to_pylist()))
    return out


def place_row(
    geographic_type: str | None,
    geographic_id: str | None,
    geographic_name: str | None,
    grades: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "geographic_type": geographic_type,
        "geographic_id": geographic_id,
        "geographic_name": geographic_name,
        "grades": grades,
        "note": note,
    }


def failure_row(note: str | None) -> dict[str, Any]:
    """One input's row when it couldn't be located."""
    return place_row(None, None, None, None, note)


def locate_rows(r: dict[str, Any], lookups: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """The rows for one located point."""
    if r.get("error") is not None:
        message = (r.get("error") or {}).get("message") or "invalid input"
        return [failure_row(f"The API couldn't locate this point: {message}.")]
    if r.get("coverage_status") == "outside_georgia":
        return [failure_row("The point is outside Georgia.")]
    rows: list[dict[str, Any]] = []
    for field, table in (
        ("county_fips", "counties"),
        ("tract_geoid", "tracts"),
        ("block_group_geoid", "block_groups"),
    ):
        code = r.get(field)
        if code is not None:
            kind = {"county_fips": "county", "tract_geoid": "tract"}.get(field, "block_group")
            rows.append(place_row(kind, str(code), (lookups.get(table) or {}).get(code)))
    district = r.get("district")
    dodea = isinstance(district, dict) and district.get("boundary_type") == "dodea"
    reason = r.get("coverage_reason")
    district_row = None
    if isinstance(district, dict):
        note = None
        if dodea:
            note = reason or (
                "Department of Defense (DoDEA) schools serve this area; they publish no zones."
            )
        district_row = place_row(
            "school_district",
            None if dodea else district.get("district_code"),
            district.get("district_name"),
            note=note,
        )
        rows.append(district_row)
    zones = r.get("zones") or []
    level_rows: list[dict[str, Any]] = []
    for level in ZONE_LEVELS:
        level_zones = [z for z in zones if z.get("zone_level") == level]
        if level_zones:
            level_rows.extend(zone_rows(level_zones, r))
            continue
        status = (r.get("level_status") or {}).get(level)
        if status is not None and status not in ("zoned", "one_school_per_grade"):
            level_rows.append(
                place_row(f"{level}_school", None, None, note=level_note(level, status, r, dodea))
            )
    if not level_rows and isinstance(reason, str) and not dodea and district_row is not None:
        district_row["note"] = reason
    out = rows + level_rows
    if not out:
        out = [failure_row(reason or "No place was found for this point.")]
    return out


def zone_rows(zones: list[dict[str, Any]], r: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows for the zones of one level, with warnings on the rows they concern."""
    out = []
    lows = [z.get("grade_low") for z in zones]
    highs = [z.get("grade_high") for z in zones]
    schools = [f"{z.get('district_code')} {z.get('school_code')}" for z in zones]
    overlap = overlapping_zones(lows, highs, schools)
    for z, lo, hi, over in zip(zones, lows, highs, overlap):
        note = None
        if (
            isinstance(r.get("currency_warning"), str)
            and z.get("currency_status") == "stale_known_changes"
        ):
            note = add_note(note, r["currency_warning"])
        if isinstance(r.get("overlap_warning"), str) and over:
            note = add_note(note, r["overlap_warning"])
        out.append(
            place_row(
                f"{z.get('zone_level')}_school",
                f"{z.get('district_code')}-{z.get('school_code')}",
                z.get("school_name"),
                format_grades(lo, hi),
                note,
            )
        )
    return out


def _grade_index(g: Any) -> int | None:
    return GRADE_CODES.index(g) if g in GRADE_CODES else None


def overlapping_zones(lo: Sequence[Any], hi: Sequence[Any], school: Sequence[str]) -> list[bool]:
    """Zones of one level whose grade runs intersect another school's."""
    los = [_grade_index(g) for g in lo]
    his = [_grade_index(g) for g in hi]
    n = len(los)
    out = [False] * n
    for i in range(n):
        for j in range(n):
            a, b, c, d = los[i], his[i], los[j], his[j]
            if (
                i != j
                and school[i] != school[j]
                and a is not None
                and b is not None
                and c is not None
                and d is not None
                and a <= d
                and c <= b
            ):
                out[i] = True
    return out


def add_note(note: str | None, text: str) -> str:
    return text if note is None else f"{note} {text}"


def level_note(level: str, status: str, r: dict[str, Any], dodea: bool = False) -> str:
    """The note for a level with no zone row."""
    reason = reason_for_level(r.get("coverage_reason"), level)

    def with_reason(text: str) -> str:
        return f"{text} {reason}" if isinstance(reason, str) and not dodea else text

    label = level[0].upper() + level[1:]
    if status == "not_available":
        if dodea:
            return f"No {level} school zone: Department of Defense (DoDEA) schools serve this area."
        return with_reason(f"No {level} school zone has been collected for this district yet.")
    if status == "gap":
        return with_reason(f"This point lies in no {level} school zone.")
    if status == "served_by_other_district":
        entries = [s for s in r.get("served_elsewhere") or [] if s.get("zone_level") == level]
        reasons = [s["reason"] for s in entries if s.get("reason")]
        if reasons:
            return " ".join(reasons)
        if entries:
            return (
                f"{label} students here are served by district {entries[0].get('district_code')}."
            )
        return f"{label} students here are served by another district."
    return with_reason(f"{label} school zone status: {status}.")


def reason_for_level(reason: Any, level: str) -> Any:
    """The part of a coverage reason about one level.

    The API's reasons often hold one paragraph per level ("Elementary: ...
    Middle: ..."); a level's row quotes only its own part, or the whole
    reason when it has no per-level parts.
    """
    if not isinstance(reason, str):
        return reason
    labels = "|".join(lv[0].upper() + lv[1:] for lv in ZONE_LEVELS)
    starts = [m.start(2) for m in re.finditer(rf"(^|(?<=[.!?] ))({labels}): ", reason)]
    if not starts:
        return reason
    ends = [*(s - 1 for s in starts[1:]), len(reason)]
    parts = [reason[s:e].strip() for s, e in zip(starts, ends)]
    mine = [p for p in parts if p.split(":", 1)[0].lower() == level]
    if not mine:
        head = reason[: starts[0]].strip()
        return head or None
    return " ".join(mine)


def format_grades(lo: Any, hi: Any) -> str | None:
    """'K-5', 'PK-5', '6-8', '9-12' (one grade: 'K', '9')."""

    def label(g: Any) -> str | None:
        if g is None or is_missing(g):
            return None
        if g in ("pk", "k"):
            return str(g).upper()
        try:
            return str(int(g))
        except (TypeError, ValueError):
            return None

    a, b = label(lo), label(hi)
    if a is None or b is None:
        return None
    return a if a == b else f"{a}-{b}"
