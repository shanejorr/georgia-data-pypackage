"""Schemas: fetching them, typing tables from them, and placing the joined
label columns.

Every result is built as a :class:`pyarrow.Table` and typed here by
:func:`apply_schema_types`, whether it was parsed from JSON or read from CSV
as text, then converted to pandas or Polars at the end (``_frames``).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from . import _cache
from ._errors import gcd_error

INTERNAL_FIELDS = ("sub_topic", "topic", "key")
"""Fields internal to the platform, dropped from everything the package
returns (:func:`contract` alone returns the contract verbatim)."""


def drop_internal(x: Any) -> Any:
    """A copy of a dict without the internal fields (other values unchanged)."""
    if isinstance(x, dict):
        return {k: v for k, v in x.items() if k not in INTERNAL_FIELDS}
    return x


# Fetching --------------------------------------------------------------------


def lookup_table_names() -> list[str]:
    """The names of the lookup tables (cached ``GET /dimensions``)."""
    listing = _cache.get_meta("dimensions")
    return [str(d["name"]) for d in listing.get("data", [])]


def dataset_schema(name: str) -> dict[str, Any]:
    """The schema of a dataset or geometry dataset (cached)."""
    schema: dict[str, Any] = _cache.get_meta(["datasets", name])
    return schema


def lookup_schema(name: str) -> dict[str, Any]:
    """The schema of a lookup table (cached)."""
    schema: dict[str, Any] = _cache.get_meta(["dimensions", name])
    return schema


def resource_kind(name: str) -> str:
    """What kind of resource a name is: ``"table"``, ``"geometry"`` or ``"lookup"``.

    Lookup tables are recognized from the cached list of lookup tables;
    anything else is asked of ``GET /datasets/{name}`` (an unknown name gives
    the API's own ``TOPIC_NOT_FOUND`` error, with suggestions).
    """
    if name in lookup_table_names():
        return "lookup"
    return str(dataset_schema(name).get("kind") or "table")


def table_schema(name: str, fn: str) -> dict[str, Any]:
    """A dataset's schema, refusing geometry datasets and lookup tables with a
    pointer to the right function."""
    check_name_arg(name, "name")
    if name in lookup_table_names():
        raise gcd_error(
            f"{name!r} is a lookup table, not a dataset.",
            [f"Use gcd.dimension({name!r}) to get its rows."],
            code="not_a_dataset",
        )
    schema = dataset_schema(name)
    if schema.get("kind") == "geometry":
        fun = (
            "gcd.district_boundaries()"
            if name == "school_district_boundaries"
            else "gcd.school_zones()"
        )
        raise gcd_error(
            f"{name!r} is a geometry dataset, which gcd.{fn}() doesn't read.",
            [f"Use {fun} instead."],
            code="not_a_dataset",
        )
    return schema


def check_name_arg(x: Any, arg: str) -> None:
    """A single non-empty string, such as a dataset name."""
    if not isinstance(x, str) or not x:
        raise TypeError(f"`{arg}` must be a single string, such as a dataset name.")


# Schema reading --------------------------------------------------------------


def schema_types(schema: Mapping[str, Any]) -> dict[str, str]:
    """Column types (column -> API type) from a schema's columns or fields."""
    cols = schema.get("columns") or schema.get("fields") or []
    return {str(c["name"]): str(c.get("type") or "string") for c in cols}


def label_columns(schema: Mapping[str, Any]) -> list[str]:
    """The joined label columns a dataset's rows carry (all strings)."""
    out: list[str] = []
    for fk in schema.get("foreign_keys") or []:
        for col in fk.get("attribute_columns_added") or []:
            if col not in out:
                out.append(str(col))
    return out


def row_types(schema: Mapping[str, Any]) -> dict[str, str]:
    """The full set of column types for a dataset's rows, joined labels included."""
    types = schema_types(schema)
    for col in label_columns(schema):
        types.setdefault(col, "string")
    return types


def code_columns(schema: Mapping[str, Any]) -> list[str]:
    """The code columns of a dataset (foreign keys to the lookup tables)."""
    return [
        str(c["name"])
        for c in schema.get("columns") or []
        if str(c.get("role") or "").startswith("fk_")
    ]


# Column order ----------------------------------------------------------------


def move_after(columns: Sequence[str], cols: Iterable[str], after: str) -> list[str]:
    """Column order with ``cols`` moved right after ``after``."""
    present = set(columns)
    moving = [c for c in cols if c in present]
    if not moving or after not in present:
        return list(columns)
    rest = [c for c in columns if c not in moving]
    at = rest.index(after) + 1
    return rest[:at] + moving + rest[at:]


def order_columns(columns: Sequence[str], first: Iterable[str]) -> list[str]:
    """The named columns first (those present), in order, then the rest."""
    present = set(columns)
    lead = [c for c in first if c in present]
    return lead + [c for c in columns if c not in lead]


def relocate_labels(columns: Sequence[str], foreign_keys: Iterable[Mapping[str, Any]]) -> list[str]:
    """Place each foreign key's joined label columns right after its code.

    Driven by the schema's ``foreign_keys[].attribute_columns_added``, so no
    list of label columns is hardcoded.
    """
    order = list(columns)
    for fk in foreign_keys or []:
        order = move_after(order, fk.get("attribute_columns_added") or [], str(fk["column"]))
    return order


def select(table: pa.Table, columns: Sequence[str]) -> pa.Table:
    """The table's columns in this order (names not present are skipped)."""
    names = set(table.column_names)
    return table.select([c for c in columns if c in names])


def drop_empty_codes(table: pa.Table, codes: Iterable[str]) -> pa.Table:
    """Drop code columns that are null on every row (kept when there are no rows)."""
    if table.num_rows == 0:
        return table
    empty = [
        c for c in codes if c in table.column_names and table.column(c).null_count == table.num_rows
    ]
    return table.drop_columns(empty) if empty else table


# Typing ----------------------------------------------------------------------

_TRUE = ("true", "t", "1")
_FALSE = ("false", "f", "0")


def apply_schema_types(table: pa.Table, types: Mapping[str, str]) -> pa.Table:
    """Type a table's columns from the schema.

    The one typing function for every result, whether it was parsed from
    JSON or read from CSV as text. ``types`` maps column names to API types:

    - ``string``: text (codes keep their leading zeros);
    - ``integer``: int64 (float64 when a value is not a whole number);
    - ``number``: float64;
    - ``boolean``: bool (``true``/``false``, ``t``/``f``, ``1``/``0``);
    - ``date``: date32;
    - ``timestamp`` / ``datetime``: timestamp in UTC.

    Columns the schema does not name are left as they are, except all-null
    ones, which become text. List and struct columns are left alone.
    """
    arrays = []
    for name in table.column_names:
        col = table.column(name).combine_chunks()
        if pa.types.is_list(col.type) or pa.types.is_struct(col.type):
            arrays.append(fix_list_type(col))
            continue
        arrays.append(convert_array(col, types.get(name)))
    return pa.table(arrays, names=table.column_names)


def fix_list_type(arr: pa.Array) -> pa.Array:
    """A list column whose values are all null becomes a list of text."""
    if pa.types.is_list(arr.type) and pa.types.is_null(arr.type.value_type):
        return arr.cast(pa.list_(pa.string()))
    return arr


def convert_array(arr: pa.Array, api_type: str | None) -> pa.Array:
    """Convert one column to an API type."""
    if api_type is None:
        return arr.cast(pa.string()) if pa.types.is_null(arr.type) else arr
    if api_type == "string":
        return _as_string(arr)
    if api_type == "integer":
        return _as_integer(arr)
    if api_type == "number":
        return _as_number(arr)
    if api_type == "boolean":
        return _as_boolean(arr)
    if api_type == "date":
        return _as_date(arr)
    if api_type in ("timestamp", "datetime"):
        return _as_timestamp(arr)
    return arr.cast(pa.string()) if pa.types.is_null(arr.type) else arr


def _is_text(arr: pa.Array) -> bool:
    return bool(pa.types.is_string(arr.type) or pa.types.is_large_string(arr.type))


def _as_string(arr: pa.Array) -> pa.Array:
    if pa.types.is_string(arr.type):
        return arr
    if pa.types.is_boolean(arr.type):
        return pa.array(
            [None if v is None else ("true" if v else "false") for v in arr.to_pylist()]
        )
    if pa.types.is_floating(arr.type):
        return pa.array(
            [None if v is None else _number_text(v) for v in arr.to_pylist()], pa.string()
        )
    return arr.cast(pa.string())


def _number_text(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else repr(x)


def _blank_to_null(arr: pa.Array) -> pa.Array:
    """Text with blanks as nulls."""
    arr = arr.cast(pa.string())
    trimmed = pc.utf8_trim_whitespace(arr)
    return pc.if_else(pc.equal(trimmed, ""), pa.scalar(None, pa.string()), trimmed)


def _whole(arr: pa.Array) -> bool:
    """Are all non-null values whole numbers within int64?"""
    valid = pc.drop_null(arr)
    if len(valid) == 0:
        return True
    if not bool(pc.all(pc.is_finite(valid)).as_py()):
        return False
    if not bool(pc.all(pc.equal(valid, pc.floor(valid))).as_py()):
        return False
    biggest = pc.max(pc.abs(valid)).as_py()
    return bool(biggest is None or biggest < 2**63 - 1)


def _as_number(arr: pa.Array) -> pa.Array:
    if pa.types.is_floating(arr.type):
        return arr.cast(pa.float64())
    if _is_text(arr):
        values = []
        for v in _blank_to_null(arr).to_pylist():
            try:
                values.append(None if v is None else float(v))
            except ValueError:
                values.append(None)
        return pa.array(values, pa.float64())
    if pa.types.is_null(arr.type) or pa.types.is_integer(arr.type) or pa.types.is_boolean(arr.type):
        return arr.cast(pa.float64())
    return arr


def _as_integer(arr: pa.Array) -> pa.Array:
    if pa.types.is_integer(arr.type):
        return arr.cast(pa.int64())
    if pa.types.is_null(arr.type):
        return arr.cast(pa.int64())
    if pa.types.is_boolean(arr.type):
        return arr.cast(pa.int64())
    if _is_text(arr):
        text = _blank_to_null(arr)
        try:
            return text.cast(pa.int64())
        except (pa.ArrowInvalid, pa.ArrowNotImplementedError):
            arr = _as_number(text)
    if pa.types.is_floating(arr.type):
        return arr.cast(pa.int64()) if _whole(arr) else arr.cast(pa.float64())
    return arr


def _as_boolean(arr: pa.Array) -> pa.Array:
    if pa.types.is_boolean(arr.type):
        return arr
    if pa.types.is_null(arr.type):
        return arr.cast(pa.bool_())
    if pa.types.is_integer(arr.type) or pa.types.is_floating(arr.type):
        return pc.not_equal(arr, 0)
    if _is_text(arr):
        out: list[bool | None] = []
        for v in arr.to_pylist():
            low = None if v is None else str(v).strip().lower()
            out.append(True if low in _TRUE else False if low in _FALSE else None)
        return pa.array(out, pa.bool_())
    return arr


def _as_date(arr: pa.Array) -> pa.Array:
    if pa.types.is_date32(arr.type):
        return arr
    if pa.types.is_null(arr.type):
        return arr.cast(pa.date32())
    if pa.types.is_timestamp(arr.type):
        return arr.cast(pa.date32())
    values: list[dt.date | None] = []
    for v in _blank_to_null(arr).to_pylist():
        try:
            values.append(None if v is None else dt.date.fromisoformat(str(v)[:10]))
        except ValueError:
            values.append(None)
    return pa.array(values, pa.date32())


TIMESTAMP_TYPE = pa.timestamp("us", tz="UTC")


def parse_utc(value: Any) -> dt.datetime | None:
    """Parse one ISO 8601 timestamp ("2026-10-29T20:17:55+00:00", "...Z", or
    no offset, meaning UTC) as an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        stamp = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        text = text.replace(" ", "T", 1)
        try:
            stamp = dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return stamp.astimezone(dt.timezone.utc)


def _as_timestamp(arr: pa.Array) -> pa.Array:
    if pa.types.is_timestamp(arr.type):
        return arr.cast(TIMESTAMP_TYPE)
    if pa.types.is_null(arr.type):
        return arr.cast(TIMESTAMP_TYPE)
    return pa.array([parse_utc(v) for v in arr.to_pylist()], TIMESTAMP_TYPE)


def empty_typed(columns: Sequence[str], types: Mapping[str, str]) -> pa.Table:
    """A zero-row table with the given columns, typed."""
    table = pa.table({c: pa.array([], pa.null()) for c in columns}) if columns else pa.table({})
    return apply_schema_types(table, types)
