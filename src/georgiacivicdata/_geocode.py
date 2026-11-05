"""Address geocoding with the U.S. Census batch geocoder, on the user's own
computer: addresses never reach the Georgia Civic Data API."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ._api import perform
from ._errors import GCDCensusError
from ._frames import is_frame
from ._params import as_values, is_missing

CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
"""The Census batch geocoder (locations, current address ranges)."""

CENSUS_BENCHMARK = "Public_AR_Current"
"""The Census benchmark the API's own address search uses."""

CENSUS_BATCH_MAX = 10000
"""The most records the Census accepts per batch file."""

ADDRESS_FIELDS = ("street", "city", "state", "zip")


@dataclass
class Addresses:
    """The ``address`` argument, normalized: one line per input, and the
    parts sent to the Census (``None`` where missing)."""

    address: list[str | None]
    street: list[str | None]
    city: list[str | None]
    state: list[str | None]
    zip: list[str | None]


@dataclass
class Geocoded:
    """One geocoded address."""

    match_status: str | None = None
    match_type: str | None = None
    matched_address: str | None = None
    lat: float | None = None
    lon: float | None = None


def _clean(v: Any) -> str | None:
    if is_missing(v):
        return None
    text = str(v).strip()
    return text or None


def _column(df: Any, name: str) -> list[Any]:
    col = df[name]
    return list(col.to_list() if hasattr(col, "to_list") else col)


def address_input(address: Any) -> Addresses:
    """Normalize the ``address`` argument.

    A string or a list of one-line addresses goes into the street field alone
    (the Census matches those as well as split fields); a data frame (pandas
    or Polars) or a dict of lists needs ``street``, ``city``, ``state`` and
    ``zip``.
    """
    if is_frame(address) or isinstance(address, dict):
        names = list(address.columns) if is_frame(address) else list(address)
        missing = [f for f in ADDRESS_FIELDS if f not in names]
        if missing:
            raise ValueError(
                "A data frame `address` needs columns street, city, state and zip "
                f"(missing: {', '.join(missing)})."
            )
        parts = {f: [_clean(v) for v in _column(address, f)] for f in ADDRESS_FIELDS}
        if not parts["street"]:
            raise ValueError("`address` has no rows.")
        one_line = [
            paste_address(s, c, st, z)
            for s, c, st, z in zip(parts["street"], parts["city"], parts["state"], parts["zip"])
        ]
        return Addresses(one_line, parts["street"], parts["city"], parts["state"], parts["zip"])
    message = (
        "`address` must be a string, a list of one-line addresses, or a data frame "
        "with street, city, state and zip columns."
    )
    try:
        values = as_values(address)
    except TypeError:
        raise TypeError(message) from None
    if not values or not all(v is None or isinstance(v, str) or is_missing(v) for v in values):
        raise TypeError(message)
    lines = [None if is_missing(v) else str(v) for v in values]
    n = len(lines)
    return Addresses(lines, [_clean(v) for v in lines], [None] * n, [None] * n, [None] * n)


def paste_address(
    street: str | None, city: str | None, state: str | None, zip_code: str | None
) -> str | None:
    """'street, city, state zip' from the parts present."""
    if street is None:
        return None
    state_zip = " ".join(p for p in (state, zip_code) if p)
    return ", ".join(p for p in (street, city, state_zip or None) if p)


def census_geocode(addresses: Addresses) -> list[Geocoded]:
    """Geocode addresses with the Census batch geocoder, in input order.

    ``match_status`` is ``"match"``, ``"no_match"``, ``"tie"``, or ``None``
    when no address was given.
    """
    out = [Geocoded() for _ in addresses.street]
    todo = [i for i, s in enumerate(addresses.street) if s is not None]
    for start in range(0, len(todo), CENSUS_BATCH_MAX):
        batch = todo[start : start + CENSUS_BATCH_MAX]
        for row_id, geo in census_batch(addresses, batch).items():
            index = int(row_id)
            if index in batch:
                out[index] = geo
    return out


def census_csv(ids: Sequence[Any], addresses: Addresses) -> str:
    """The upload: id, street, city, state, ZIP, every field quoted."""

    def q(x: Any) -> str:
        text = "" if x is None else str(x)
        return '"' + text.replace('"', '""') + '"'

    lines = []
    for i in ids:
        fields = (i, addresses.street[i], addresses.city[i], addresses.state[i], addresses.zip[i])
        lines.append(",".join(q(f) for f in fields))
    return "\n".join(lines) + "\n"


def census_batch(addresses: Addresses, ids: Sequence[int]) -> dict[str, Geocoded]:
    """Send one batch file to the Census and parse the answer."""
    upload = census_csv(ids, addresses).encode("utf-8")
    resp = perform(
        "POST",
        CENSUS_BATCH_URL,
        files={"addressFile": ("addresses.csv", upload, "text/csv")},
        data={"benchmark": CENSUS_BENCHMARK},
        timeout=1800,
        service="census",
        max_tries=3,
        max_seconds=3600,
    )
    return parse_census(resp.text)


def parse_census(text: str) -> dict[str, Geocoded]:
    """Parse the Census response CSV (no header; unmatched rows are short)."""
    out: dict[str, Geocoded] = {}
    if not text.strip():
        return out
    try:
        reader = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise GCDCensusError(
            "Couldn't read the U.S. Census geocoder's response.", code="CENSUS_PARSE"
        ) from exc
    for row in reader:
        if not row:
            continue
        row = row + [""] * (8 - len(row))
        status = row[2].strip().lower() or None
        lat = lon = None
        if status == "match" and row[5]:
            try:
                lon_text, lat_text = row[5].split(",")[:2]
                lon, lat = float(lon_text), float(lat_text)
            except ValueError:
                lat = lon = None
        out[row[0].strip()] = Geocoded(
            match_status=status,
            match_type=row[3].strip().lower() or None,
            matched_address=row[4] or None,
            lat=lat,
            lon=lon,
        )
    return out
