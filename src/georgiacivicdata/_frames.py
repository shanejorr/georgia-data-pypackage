"""Building tables from JSON records, converting them to pandas or Polars,
and the metadata that travels with each result."""

from __future__ import annotations

import json
import weakref
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

import pandas as pd
import pyarrow as pa

from ._options import resolve_backend
from ._schema import fix_list_type

if TYPE_CHECKING:
    import polars as pl

    Frame = pd.DataFrame | pl.DataFrame
else:
    Frame = Any


# Records to Arrow -------------------------------------------------------------


def _text(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def make_array(values: list[Any], as_list: bool = False) -> pa.Array:
    """One column from JSON values: scalars become a typed array (text when
    the values mix types); arrays become a list column."""
    if as_list or any(isinstance(v, (list, tuple)) for v in values):
        items = [
            list(v) if isinstance(v, (list, tuple)) else ([] if v is None else [v]) for v in values
        ]
        try:
            return fix_list_type(pa.array(items))
        except (pa.ArrowInvalid, pa.ArrowTypeError, TypeError, OverflowError):
            texts = [[_text(e) for e in v] for v in items]
            return pa.array(texts, pa.list_(pa.string()))
    try:
        return pa.array(values)
    except (pa.ArrowInvalid, pa.ArrowTypeError, TypeError, OverflowError):
        return pa.array([_text(v) for v in values], pa.string())


def records_to_table(
    records: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
    list_cols: Iterable[str] = (),
) -> pa.Table:
    """A list of JSON records (dicts) as an Arrow table.

    Scalar fields become columns; arrays become list columns. ``list_cols``
    forces fields to list columns even when every value is scalar.
    ``fields`` fixes the columns and their order (missing fields are null).
    """
    list_cols = set(list_cols)
    if fields is None:
        seen: dict[str, None] = {}
        for record in records:
            for key in record:
                seen.setdefault(key, None)
        fields = list(seen)
    if not records:
        arrays = [
            pa.array([], pa.list_(pa.string())) if f in list_cols else pa.array([], pa.null())
            for f in fields
        ]
        return pa.table(arrays, names=list(fields)) if fields else pa.table({})
    arrays = [make_array([r.get(f) for r in records], as_list=f in list_cols) for f in fields]
    return pa.table(arrays, names=list(fields))


def columns_to_table(columns: Mapping[str, Sequence[Any]]) -> pa.Table:
    """A table from a mapping of column name to Python values."""
    return pa.table({name: make_array(list(values)) for name, values in columns.items()})


# Arrow to pandas or Polars ---------------------------------------------------


def _pandas_type(arrow_type: pa.DataType) -> Any:
    """Nullable pandas dtypes: integers ``Int64``, booleans ``boolean``, text
    ``string``; floats stay ``float64`` (missing is ``NaN``)."""
    if pa.types.is_integer(arrow_type):
        return pd.Int64Dtype()
    if pa.types.is_boolean(arrow_type):
        return pd.BooleanDtype()
    if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
        return pd.StringDtype()
    return None


def _null_to_text(table: pa.Table) -> pa.Table:
    arrays = [
        table.column(i).cast(pa.string())
        if pa.types.is_null(table.schema.field(i).type)
        else table.column(i)
        for i in range(table.num_columns)
    ]
    return pa.table(arrays, names=table.column_names)


def to_pandas(table: pa.Table) -> pd.DataFrame:
    """Arrow to pandas with nullable dtypes; list columns hold Python lists."""
    table = _null_to_text(table)
    df: pd.DataFrame = table.to_pandas(
        types_mapper=_pandas_type, date_as_object=False, ignore_metadata=True
    )
    for field in table.schema:
        if pa.types.is_list(field.type) or pa.types.is_large_list(field.type):
            df[field.name] = pd.Series(
                [[] if v is None else list(v) for v in table.column(field.name).to_pylist()],
                index=df.index,
                dtype=object,
            )
        elif pa.types.is_struct(field.type):
            df[field.name] = pd.Series(
                table.column(field.name).to_pylist(), index=df.index, dtype=object
            )
    return df


def to_polars(table: pa.Table) -> pl.DataFrame:
    """Arrow to Polars."""
    polars = import_polars()
    out: pl.DataFrame = polars.from_arrow(_null_to_text(table))
    return out


def import_polars() -> Any:
    try:
        import polars
    except ImportError as exc:
        raise ImportError(
            "backend='polars' needs the 'polars' package. Install it with "
            "`pip install georgiacivicdata[polars]` (or `pip install polars`)."
        ) from exc
    return polars


def to_frame(table: pa.Table, backend: str | None, info: dict[str, Any] | None = None) -> Frame:
    """Convert a finished table to the requested backend and attach its
    metadata."""
    backend = resolve_backend(backend)
    frame = to_polars(table) if backend == "polars" else to_pandas(table)
    if info is not None:
        attach(frame, info)
    return frame


def is_frame(x: Any) -> bool:
    if isinstance(x, pd.DataFrame):
        return True
    return type(x).__module__.startswith("polars") and type(x).__name__ == "DataFrame"


# Metadata --------------------------------------------------------------------

_REGISTRY: dict[int, dict[str, Any]] = {}


def attach(frame: Any, info: dict[str, Any]) -> Any:
    """Attach metadata to a result.

    Polars data frames have no attributes, so metadata lives in a registry
    keyed by the object (cleared when the object is garbage collected). A
    pandas result also carries it in ``df.attrs["gcd_meta"]``, which pandas
    keeps through some operations.
    """
    key = id(frame)
    _REGISTRY[key] = info
    weakref.finalize(frame, _REGISTRY.pop, key, None)
    if isinstance(frame, pd.DataFrame):
        frame.attrs["gcd_meta"] = info
    return frame


def attached(frame: Any) -> dict[str, Any] | None:
    """The metadata attached to a result, or ``None``."""
    info = _REGISTRY.get(id(frame))
    if info is None and isinstance(frame, pd.DataFrame):
        value = frame.attrs.get("gcd_meta")
        info = value if isinstance(value, dict) else None
    return info
