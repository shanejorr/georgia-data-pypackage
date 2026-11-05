"""Places by name: one shared resolver turns district, school and county
names into codes before any data request."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Any

import pyarrow as pa

from . import _cache
from ._errors import (
    GCDError,
    GCDPlaceAmbiguousError,
    GCDPlaceNotFoundError,
    gcd_error,
    quote_list,
)
from ._params import Places, as_names

# Letters NFKD does not decompose, curly quotes and dashes (escaped so the
# source stays ASCII).
_FOLD = str.maketrans(
    {
        "\u00d8": "O",
        "\u00f8": "o",
        "\u0110": "D",
        "\u0111": "d",
        "\u0141": "L",
        "\u0142": "l",
        "\u0131": "i",
        "\u0126": "H",
        "\u0127": "h",
        "\u2018": "'",
        "\u2019": "'",
        "\u02bc": "'",
        "\u2013": "-",
        "\u2014": "-",
    }
)


def normalize_place(x: str) -> str:
    """Normalize a place name for exact matching.

    Ignores case, accents, surrounding and repeated whitespace, and a
    trailing " County" (so "Fulton County", "fulton" and " FULTON " match).
    """
    s = unicodedata.normalize("NFKD", str(x))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.translate(_FOLD).lower()
    s = re.sub(r"\s+", " ", s.strip())
    return re.sub(r" county$", "", s)


def _col(table: pa.Table, name: str) -> list[Any]:
    if name not in table.column_names:
        return [None] * table.num_rows
    return list(table.column(name).to_pylist())


def name_index(table: pa.Table, name_col: str) -> dict[str, list[int]]:
    """The matching index of a lookup table: normalized name -> rows,
    covering the current name and every former name."""

    def build() -> dict[str, list[int]]:
        index: dict[str, list[int]] = {}
        current = _col(table, name_col)
        former = _col(table, "former_names")
        for i, (name, old) in enumerate(zip(current, former)):
            names = [name] if name is not None else []
            if old:
                names.extend(str(old).split("; "))
            for n in {normalize_place(v) for v in names}:
                index.setdefault(n, []).append(i)
        return index

    return _cache.cache_get_or_set(f"index:{name_col}", build)


def match_place_rows(value: str, table: pa.Table, name_col: str) -> list[int]:
    """Rows of a lookup table whose current or former name matches exactly."""
    return sorted(set(name_index(table, name_col).get(normalize_place(value), [])))


def _lookup(name: str) -> pa.Table:
    from ._dimension import lookup_table

    return lookup_table(name)


def resolve_places(
    district: Any = None,
    school: Any = None,
    county: Any = None,
    filters: dict[str, list[str]] | None = None,
    columns: Sequence[str] | None = None,
    target: str | None = None,
) -> Places:
    """Turn place names into codes.

    ``filters`` are the encoded filters, to read codes given alongside;
    ``columns`` are the target's columns: a name argument whose code column
    is missing is an error before any request.
    """
    district = as_names(district, "district")
    school = as_names(school, "school")
    county = as_names(county, "county")
    filters = filters or {}
    out = Places()
    if district is None and school is None and county is None:
        return out
    _code_or_name(district, filters.get("district_code"), "district", "district_code")
    _code_or_name(county, filters.get("county_fips"), "county", "county_fips")
    _code_or_name(school, filters.get("school_code"), "school", "school_code")
    _code_or_name(school, filters.get("school"), "school", "school_id")
    if columns is not None:
        _place_columns(district, "district", ["district_code"], columns, target)
        _place_columns(county, "county", ["county_fips"], columns, target)
        _place_columns(school, "school", ["district_code", "school_code"], columns, target)

    district_codes: list[str] | None = None
    if district is not None:
        district_codes = _resolve_simple(
            district, "districts", "district_name", "district_code", "district"
        )
    if county is not None:
        out.county_fips = _resolve_simple(
            county, "counties", "county_name", "county_fips", "county"
        )
    if school is not None:
        context: list[str] = []
        for code in (district_codes or []) + (filters.get("district_code") or []):
            if code not in context:
                context.append(code)
        schools = _resolve_schools(school, context)
        out.schools = schools
        out.school_pairs = [f"{d}-{s}" for d, s in schools]
    else:
        out.district_code = district_codes
    return out


def _code_or_name(name: Any, code: Any, name_arg: str, code_arg: str) -> None:
    if name is not None and code is not None:
        raise ValueError(f"Give `{name_arg}` or `{code_arg}`, not both.")


def _place_columns(
    name: Any, arg: str, needs: list[str], columns: Sequence[str], target: str | None
) -> None:
    if name is None:
        return
    missing = [c for c in needs if c not in columns]
    if missing:
        what = target or "This dataset"
        plural = "s" if len(missing) > 1 else ""
        raise gcd_error(
            f"`{arg}` doesn't apply: {what} has no {' or '.join(missing)} column{plural}.",
            ["Check the columns with gcd.columns()."],
            code="place_not_applicable",
        )


def _unique(values: Sequence[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        if v not in out:
            out.append(v)
    return out


def _resolve_simple(
    names: list[str], table_name: str, name_col: str, key: str, arg: str
) -> list[str]:
    """Resolve district or county names to codes (one code per name)."""
    table = _lookup(table_name)
    keys = _col(table, key)
    labels = _col(table, name_col)
    codes: list[str] = []
    for value in _unique(names):
        rows = match_place_rows(value, table, name_col)
        if not rows:
            raise _place_not_found(value, arg, table_name, name_col)
        hits = _unique([keys[i] for i in rows])
        if len(hits) > 1:
            lines = [f"{keys[i]}: {labels[i]}" for i in rows]
            raise _place_ambiguous(value, arg, lines, f"Use `{key}` with one of these codes.")
        codes.extend(hits)
    return _unique(codes)


def _resolve_schools(names: list[str], districts: list[str]) -> list[tuple[str, str]]:
    """Resolve school names to (district, school) pairs.

    A name must identify one school per district: with no district given it
    must exist in one district only, and within a district two schools with
    one name (an old and a new one) are ambiguous.
    """
    table = _lookup("schools")
    dcodes = _col(table, "district_code")
    scodes = _col(table, "school_code")
    pairs: list[tuple[str, str]] = []
    for value in _unique(names):
        rows = match_place_rows(value, table, "school_name")
        in_context = [i for i in rows if dcodes[i] in districts] if districts else rows
        if not in_context:
            raise _place_not_found(
                value,
                "school",
                "schools",
                "school_name",
                districts=districts,
                elsewhere=_unique([dcodes[i] for i in rows]),
            )
        per_district = Counter(dcodes[i] for i in in_context)
        if len(per_district) > 1 and not districts:
            raise _place_ambiguous(
                value,
                "school",
                _school_lines(table, in_context),
                "Add `district` (or `district_code`) to pick one.",
                n_districts=len(per_district),
            )
        if any(n > 1 for n in per_district.values()):
            raise _place_ambiguous(
                value,
                "school",
                _school_lines(table, in_context),
                "Use `school_id` with one 'DISTRICT-SCHOOL' code.",
            )
        for i in in_context:
            pair = (dcodes[i], scodes[i])
            if pair not in pairs:
                pairs.append(pair)
    return pairs


def _school_lines(table: pa.Table, rows: list[int]) -> list[str]:
    """Candidate lines for a school error."""
    districts = _lookup("districts")
    dnames = dict(zip(_col(districts, "district_code"), _col(districts, "district_name")))
    dcodes = _col(table, "district_code")
    scodes = _col(table, "school_code")
    names = _col(table, "school_name")
    active = _col(table, "active")
    lines = []
    for i in rows:
        state = "" if active[i] is None else (", active" if active[i] else ", inactive")
        lines.append(f"{dcodes[i]}-{scodes[i]}: {names[i]} ({dnames.get(dcodes[i])}{state})")
    return lines


def _district_labels(codes: Sequence[str]) -> str:
    """'Fulton County (660)' for district codes, from the cached table."""
    try:
        table = _lookup("districts")
        names = dict(zip(_col(table, "district_code"), _col(table, "district_name")))
    except GCDError:
        names = {}
    labels = [f"{names[c]} ({c})" if names.get(c) else f"district {c}" for c in codes]
    return ", ".join(labels)


def _place_not_found(
    value: str,
    arg: str,
    table_name: str,
    name_col: str,
    districts: Sequence[str] | None = None,
    elsewhere: Sequence[str] = (),
) -> GCDError:
    """No exact match for a place name."""
    lead = f"No {arg} named {value!r}."
    bullets: list[str] = []
    if districts:
        lead = f"No school named {value!r} in {_district_labels(districts)}."
        if elsewhere:
            bullets.append(f"A school with that name is in {_district_labels(elsewhere)}.")
    suggestions = _place_suggestions(value, table_name, name_col, districts)
    if not suggestions:
        suggestions = near_names(value, table_name, name_col, districts)
    if suggestions:
        bullets.append(f"Did you mean: {quote_list(suggestions)}?")
    q = re.sub(r" county$", "", value.strip().lower())
    bullets.append(
        "Names match exactly (ignoring case and accents); browse with "
        f"gcd.dimension({table_name!r}, q={q!r})."
    )
    return gcd_error(
        lead,
        bullets,
        code="place_not_found",
        details={"input": value, "suggestions": suggestions},
        cls=GCDPlaceNotFoundError,
    )


def _place_ambiguous(
    value: str, arg: str, lines: list[str], hint: str, n_districts: int | None = None
) -> GCDError:
    """More than one match for a place name."""
    if n_districts is None:
        lead = f"{value!r} matches more than one {arg}."
    else:
        lead = f"{value!r} names schools in {n_districts} districts."
    shown = lines[:10]
    bullets = [hint] + [f"* {line}" for line in shown]
    if len(lines) > len(shown):
        bullets.append(f"... and {len(lines) - len(shown)} more.")
    return gcd_error(
        lead,
        bullets,
        code="place_ambiguous",
        details={"input": value, "candidates": lines},
        cls=GCDPlaceAmbiguousError,
    )


def _place_suggestions(
    value: str, table_name: str, name_col: str, districts: Sequence[str] | None = None
) -> list[str]:
    """Near names from the lookup table's text search (best effort)."""
    from ._api import get_json

    q = re.sub(r" county$", "", value.strip(), flags=re.IGNORECASE)
    words = sorted(q.split(), key=len, reverse=True)
    queries = _unique([q, *words[:1]])
    for text in queries:
        if len(text) < 3:
            continue
        query = {"q": [text], "limit": ["5"], "columns": [name_col]}
        if districts and table_name == "schools":
            query["district_code"] = list(districts)
        try:
            found = get_json(["dimensions", table_name, "rows"], query)
        except GCDError:
            continue
        names = _unique([r.get(name_col) for r in found.get("data") or [] if r.get(name_col)])
        if names:
            return names
    return []


def levenshtein(a: str, b: str) -> int:
    """Edit distance (insertions, deletions and substitutions cost 1)."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def near_names(
    value: str, table_name: str, name_col: str, districts: Sequence[str] | None = None
) -> list[str]:
    """Close spellings from the cached lookup table (suggestions only: a
    place is never matched this way)."""
    try:
        table = _lookup(table_name)
    except GCDError:
        return []
    names = _col(table, name_col)
    if districts and "district_code" in table.column_names:
        codes = _col(table, "district_code")
        names = [n for n, c in zip(names, codes) if c in districts]
    names = _unique([n for n in names if n])
    if not names:
        return []
    target = normalize_place(value)
    limit = max(2, math.floor(len(target) * 0.25))
    scored = [(levenshtein(target, normalize_place(n)), i, n) for i, n in enumerate(names)]
    keep = sorted((d, i, n) for d, i, n in scored if d <= limit)
    return [n for _, _, n in keep[:3]]
