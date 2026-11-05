"""Understand a dataset: :func:`describe`, :func:`columns` and :func:`contract`."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, overload

import pandas as pd
import pyarrow as pa

from . import _cache
from ._api import build_url, perform
from ._errors import GCDNotFoundError, gcd_error
from ._frames import Frame, records_to_table, to_frame
from ._options import resolve_backend
from ._params import check_flag
from ._schema import (
    apply_schema_types,
    check_name_arg,
    dataset_schema,
    drop_internal,
    lookup_schema,
    lookup_table_names,
    parse_utc,
    resource_kind,
)

if TYPE_CHECKING:
    import polars as pl

COLUMN_FIELDS = (
    "column",
    "label",
    "type",
    "role",
    "label_of",
    "unit",
    "is_key_metric",
    "metric_component",
    "nullable",
    "valid_values",
    "description",
    "null_meaning",
)
COLUMN_TYPES = {
    "column": "string",
    "label": "string",
    "type": "string",
    "role": "string",
    "label_of": "string",
    "unit": "string",
    "is_key_metric": "boolean",
    "metric_component": "string",
    "nullable": "boolean",
    "description": "string",
    "null_meaning": "string",
}
FILTER_FIELDS = (
    "param",
    "kind",
    "values",
    "multi_value",
    "has_total",
    "total_value",
    "requires_single_value",
    "nullable",
)
FILTER_TYPES = {
    "param": "string",
    "kind": "string",
    "multi_value": "boolean",
    "has_total": "boolean",
    "total_value": "string",
    "requires_single_value": "boolean",
    "nullable": "boolean",
}


@dataclass(repr=False)
class Description:
    """Everything about one dataset, lookup table or geometry dataset.

    Returned by :func:`describe`. ``print()`` (or the notebook display)
    shows a readable summary; the attributes hold the parts.

    Attributes
    ----------
    name, kind, title, summary, description : str or None
        What it is. ``kind`` is ``"table"``, ``"geometry"`` or ``"lookup"``.
    main_topic, source, source_url, update_frequency : str or None
        Where it comes from.
    updated_at : datetime.datetime or None
        When the data last changed (UTC).
    years, year_gaps : list of int
        The years covered, and the years missing inside that span.
    detail_levels, default_detail, grain, key_metric :
        The detail levels (and the default), the columns that identify a
        row, and the headline metric.
    primary_key, search_columns : list of str
        For lookup tables: the key, and the columns ``q`` searches.
    crs, formats :
        For geometry datasets: the coordinate system and download formats.
    columns : DataFrame
        The column dictionary, as :func:`columns` returns it by default.
    filters : DataFrame
        Every filter parameter: ``param``, ``kind``, ``values`` (list
        column), ``multi_value``, ``has_total``, ``total_value``,
        ``requires_single_value`` and ``nullable``.
    notes : dict
        The contract's declarations that are present, each a data frame, a
        string or a dict (see :func:`describe`).
    raw : dict
        The full parsed schema response, without platform-internal fields.
    """

    name: str
    kind: str
    title: str | None = None
    summary: str | None = None
    description: str | None = None
    main_topic: str | None = None
    source: str | None = None
    source_url: str | None = None
    update_frequency: str | None = None
    updated_at: dt.datetime | None = None
    years: list[int] = field(default_factory=list)
    year_gaps: list[int] = field(default_factory=list)
    detail_levels: list[str] = field(default_factory=list)
    default_detail: str | None = None
    grain: list[str] = field(default_factory=list)
    key_metric: str | None = None
    primary_key: list[str] = field(default_factory=list)
    search_columns: list[str] = field(default_factory=list)
    crs: str | None = None
    formats: list[str] = field(default_factory=list)
    columns: Any = None
    filters: Any = None
    notes: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    _n_own: int = 0
    _n_label: int = 0
    _filter_params: list[str] = field(default_factory=list)
    _single: list[str] = field(default_factory=list)
    _column_names: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        """The summary as lines of text (unwrapped)."""
        if self.kind == "lookup":
            return _lines_lookup(self)
        if self.kind == "geometry":
            return _lines_geometry(self)
        return _lines_table(self)

    def format(self, width: int | None = None) -> str:
        """The summary as text, wrapped to ``width`` (default: the terminal)."""
        if width is None:
            width = shutil.get_terminal_size(fallback=(80, 24)).columns
        out: list[str] = []
        for line in self.lines():
            if len(line) <= width or line.startswith("--"):
                out.append(line[:width] if line.startswith("--") else line)
                continue
            indent = "  " if line.startswith("* ") else ""
            out.extend(textwrap.wrap(line, width=width, subsequent_indent=indent) or [""])
        return "\n".join(out)

    def __repr__(self) -> str:
        return self.format()

    def __str__(self) -> str:
        return self.format()


# Public functions -------------------------------------------------------------


def describe(name: str, *, backend: Literal["pandas", "polars"] | None = None) -> Description:
    """Describe a dataset or lookup table.

    Everything about one dataset, lookup table or geometry dataset: what it
    holds, its source, years, detail levels, the columns that identify a row
    (the grain), its key metric, every filter, and the notes its data
    contract declares (limitations, series breaks, groups that must not be
    added up, and so on). Printing the result shows a readable summary.

    Read the **"Pick one value of"** line: it names categorical columns with
    no total (such as ``grade_cluster``), whose values must not be mixed in
    one summary. :func:`rows` returns every value of them unless you filter
    one.

    The ``filters`` table is also how to discover the filters that are not
    columns of the dataset: lookup-table attributes such as
    ``district_type``, ``school_level``, ``locale`` and
    ``demographic_category``.

    Parameters
    ----------
    name : str
        A dataset, lookup table or geometry dataset name, such as
        ``"graduation_rate_4_year_cohort"``, ``"schools"`` or
        ``"school_attendance_zones"``. Names are unique across all three
        kinds.
    backend : {"pandas", "polars"}, optional
        The kind of data frame for the ``columns``, ``filters`` and table
        ``notes``. Default: the ``backend`` option.

    Returns
    -------
    Description
        Attributes include ``name``, ``kind`` (``"table"``, ``"geometry"`` or
        ``"lookup"``), ``title``, ``summary``, ``description``, ``source``,
        ``source_url``, ``years``, ``year_gaps``, ``detail_levels``,
        ``default_detail``, ``grain``, ``key_metric``, and:

        - ``columns``: the column dictionary, as :func:`columns` returns it
          by default (for a dataset, the joined name columns included).
        - ``filters``: a data frame of every filter parameter: ``param``,
          ``kind`` (categorical, foreign_key, dimension_attribute,
          metric_bound, year, detail, ...), ``values`` (list column of
          allowed values), ``multi_value``, ``has_total``, ``total_value``,
          ``requires_single_value`` and ``nullable``.
        - ``notes``: the contract's declarations that are present:
          ``limitations``, ``year_meaning`` (strings), ``null_semantics`` (a
          dict), ``series_breaks``, ``non_additive``, ``partitions``,
          ``pooled_rates``, ``year_window``, ``value_implications``,
          ``pooled_min_count`` (data frames), and ``assignment_note`` for the
          zones.
        - ``raw``: the full parsed schema response.

    See Also
    --------
    columns : the column table alone.
    values : the category values present under a filter.
    contract : the formal contract.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.describe("graduation_rate_4_year_cohort")  # doctest: +SKIP
    >>> gcd.describe("ccrpi_content_mastery").filters  # doctest: +SKIP
    >>> gcd.describe("schools")  # doctest: +SKIP
    """
    check_name_arg(name, "name")
    chosen = resolve_backend(backend)
    kind = resource_kind(name)
    if kind == "lookup":
        return _describe_lookup(lookup_schema(name), chosen)
    if kind == "geometry":
        return _describe_geometry(dataset_schema(name), chosen)
    return _describe_table(dataset_schema(name), chosen)


@overload
def columns(name: str, labels: bool = ..., *, backend: Literal["pandas"]) -> pd.DataFrame: ...
@overload
def columns(name: str, labels: bool = ..., *, backend: Literal["polars"]) -> pl.DataFrame: ...
@overload
def columns(name: str, labels: bool = ..., *, backend: None = ...) -> Frame: ...
def columns(
    name: str, labels: bool = True, *, backend: Literal["pandas", "polars"] | None = None
) -> Frame:
    """Get a dataset's column dictionary.

    The columns of a dataset, lookup table or geometry dataset as a tidy
    table: what each column means, its type, its unit and, for metrics,
    whether it is a numerator or denominator. This is the place to check
    "what does ``pct_proficient_learner_or_above`` mean, and is it 0-1?".

    The dictionary lists every column a dataset can return. Which ones a
    given :func:`rows` call returns also depends on its ``detail`` and
    ``columns``: code columns that would be empty on every row (a county
    row's ``tract_geoid``, a district row's ``school_code``) are left out.

    Parameters
    ----------
    name : str
        A dataset, lookup table or geometry dataset name.
    labels : bool, default True
        ``True`` also lists the name columns that :func:`rows` joins in by
        default (``district_name``, ``county_name``, ``demographic_label``,
        ...), each right after its code, with ``role`` ``"label"``.
        ``False`` lists the dataset's own columns only, matching
        ``rows(labels=False)``. Labels come only with datasets; lookup tables
        and geometry datasets ignore this argument.
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        One row per column, with columns:

        - ``column``: the column name.
        - ``label``: a short display name.
        - ``type``: ``"integer"``, ``"number"``, ``"string"``, ``"boolean"``
          or ``"date"``, which :func:`rows` maps to integer, float, string,
          boolean and date columns.
        - ``role``: ``"year"``, a foreign key (``"fk_district"``,
          ``"fk_school"``, ...), ``"categorical"``, ``"metric"`` or
          ``"label"`` (a joined name column) for datasets; ``"key"`` or
          ``"attribute"`` for lookup tables.
        - ``label_of``: for a ``"label"`` column, the code column it names
          (``"district_code"``, ``"demographic"``, ...); otherwise missing.
        - ``unit``: ``"count"``, ``"proportion"`` (0-1 scale), a rate unit,
          ...
        - ``is_key_metric``: boolean, true for the dataset's headline metric.
        - ``metric_component``: ``"numerator"`` or ``"denominator"`` for the
          counts a rate is built from.
        - ``nullable``: boolean.
        - ``valid_values``: list column of a categorical column's values.
        - ``description``: the full definition.
        - ``null_meaning``: what a missing value means in this column.

        Fields that don't apply (labels and units for lookup tables and
        joined name columns, most fields for geometry datasets) are missing.
        A joined name column's ``description`` and ``nullable`` come from its
        lookup table; see :func:`dimension`.

    See Also
    --------
    describe : the whole schema.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.columns("graduation_rate_4_year_cohort")  # doctest: +SKIP
    >>> gcd.columns("graduation_rate_4_year_cohort", labels=False)  # doctest: +SKIP
    >>> gcd.columns("schools")  # doctest: +SKIP
    """
    check_name_arg(name, "name")
    check_flag(labels, "labels")
    resolve_backend(backend)
    kind = resource_kind(name)
    if kind == "lookup":
        return to_frame(_columns_table(column_records(lookup_schema(name), kind)), backend)
    schema = dataset_schema(name)
    records = column_records(schema, kind)
    if labels and kind == "table":
        records = add_label_records(records, schema)
    return to_frame(_columns_table(records), backend)


@overload
def contract(name: str, file: None = ...) -> dict[str, Any]: ...
@overload
def contract(name: str, file: str | os.PathLike[str]) -> str | os.PathLike[str]: ...
def contract(
    name: str, file: str | os.PathLike[str] | None = None
) -> dict[str, Any] | str | os.PathLike[str]:
    """Get a dataset's data contract.

    The dataset's formal, versioned contract in the Open Data Contract
    Standard (ODCS v3.2): its schema, quality rules, ``version`` and
    ``schema_hash``. For data engineers building pipelines and anyone citing
    the exact schema. Most users want :func:`describe` instead.

    Datasets and the ``school_attendance_zones`` geometry dataset have
    contracts; lookup tables and ``school_district_boundaries`` do not.

    Parameters
    ----------
    name : str
        A dataset name.
    file : str or path-like, optional
        If given, the contract is written there verbatim as YAML and the path
        is returned. Default: return the contract as a dict.

    Returns
    -------
    dict or path
        The contract as a nested dict (parsed from its JSON form), or, with
        ``file``, the path.

    See Also
    --------
    describe : a readable summary.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> spec = gcd.contract("graduation_rate_4_year_cohort")  # doctest: +SKIP
    >>> spec["version"]  # doctest: +SKIP
    >>> gcd.contract("graduation_rate_4_year_cohort", file="contract.yaml")  # doctest: +SKIP
    """
    check_name_arg(name, "name")
    if file is not None and not isinstance(file, (str, os.PathLike)):
        raise TypeError("`file` must be a single path.")
    if name in lookup_table_names():
        raise gcd_error(
            "Lookup tables have no contract route.",
            [f"Use gcd.describe({name!r}) for the schema of {name!r}."],
            code="no_contract",
        )
    path = ["datasets", name, "contract"]
    try:
        if file is None:
            spec: dict[str, Any] = _cache.get_meta(path, {"format": ["json"]})
            return spec
        resp = perform("GET", build_url(path, {"format": ["yaml"]}))
    except GCDNotFoundError as err:
        if err.code == "TOPIC_NOT_FOUND" and resource_kind(name) == "geometry":
            raise gcd_error(
                f"The geometry dataset {name!r} has no contract route.",
                [f"Use gcd.describe({name!r}) for its fields."],
                code="no_contract",
            ) from None
        raise
    with open(file, "wb") as fh:
        fh.write(resp.bytes)
    return file


# Builders --------------------------------------------------------------------


def _ints(x: Any) -> list[int]:
    return [int(v) for v in x or []]


def _strs(x: Any) -> list[str]:
    return [str(v) for v in x or []]


def _describe_table(schema: Mapping[str, Any], backend: str) -> Description:
    records = add_label_records(column_records(schema, "table"), schema)
    filters = _filters_table(schema)
    d = Description(
        name=str(schema.get("name")),
        kind="table",
        title=schema.get("title"),
        summary=schema.get("summary"),
        description=schema.get("description"),
        main_topic=schema.get("main_topic"),
        source=schema.get("source"),
        source_url=schema.get("source_url"),
        update_frequency=schema.get("update_frequency"),
        updated_at=parse_utc(schema.get("updated_at")),
        years=_ints(schema.get("available_years")),
        year_gaps=_ints(schema.get("year_gaps")),
        detail_levels=_strs(schema.get("detail_levels")),
        default_detail=schema.get("default_detail"),
        grain=_strs(schema.get("grain")),
        key_metric=schema.get("key_metric"),
        columns=to_frame(_columns_table(records), backend),
        filters=to_frame(filters, backend),
        notes=_notes(schema, backend),
        raw=drop_internal(dict(schema)),
    )
    d._n_label = sum(1 for r in records if r.get("role") == "label")
    d._n_own = len(records) - d._n_label
    d._filter_params = [str(p) for p in filters.column("param").to_pylist()]
    d._single = [
        str(f.get("param"))
        for f in schema.get("filters") or []
        if f.get("requires_single_value") is True
    ]
    return d


def _describe_lookup(schema: Mapping[str, Any], backend: str) -> Description:
    records = column_records(schema, "lookup")
    filters = _lookup_filters_table(schema)
    notes = {k: schema[k] for k in ("notes", "semantics") if schema.get(k) is not None}
    search = schema.get("search") or {}
    d = Description(
        name=str(schema.get("name")),
        kind="lookup",
        title=schema.get("name"),
        description=schema.get("description"),
        primary_key=_strs(schema.get("primary_key")),
        search_columns=_strs(search.get("columns")),
        columns=to_frame(_columns_table(records), backend),
        filters=to_frame(filters, backend),
        notes=notes,
        raw=drop_internal(dict(schema)),
    )
    d._column_names = [str(r["column"]) for r in records]
    d._filter_params = [str(p) for p in filters.column("param").to_pylist()]
    return d


def _describe_geometry(schema: Mapping[str, Any], backend: str) -> Description:
    description = schema.get("description")
    purpose = description.get("purpose") if isinstance(description, dict) else description
    records = column_records(schema, "geometry")
    filters = _geometry_filters_table(schema)
    notes = {
        k: schema[k]
        for k in ("limitations", "note", "assignment_note")
        if schema.get(k) is not None
    }
    d = Description(
        name=str(schema.get("name")),
        kind="geometry",
        title=str(schema.get("name") or "").replace("_", " "),
        description=purpose,
        source=schema.get("source"),
        crs=schema.get("crs"),
        grain=_strs(schema.get("grain")),
        formats=_strs(schema.get("formats")),
        columns=to_frame(_columns_table(records), backend),
        filters=to_frame(filters, backend),
        notes=notes,
        raw=drop_internal(dict(schema)),
    )
    d._n_own = len(records)
    d._filter_params = [str(p) for p in filters.column("param").to_pylist()]
    return d


def column_records(schema: Mapping[str, Any], kind: str) -> list[dict[str, Any]]:
    """The column dictionary for any kind of schema, as records."""
    cols = schema.get("fields") if kind == "geometry" else schema.get("columns")
    key_metric = schema.get("key_metric")
    values_field = "enum" if kind == "geometry" else "valid_values"
    out = []
    for c in cols or []:
        out.append(
            {
                "column": c.get("name"),
                "label": c.get("label"),
                "type": c.get("type"),
                "role": c.get("role"),
                "label_of": None,
                "unit": c.get("unit"),
                "is_key_metric": key_metric is not None and c.get("name") == key_metric,
                "metric_component": c.get("metric_component"),
                "nullable": c.get("nullable"),
                "valid_values": list(c.get(values_field) or []),
                "description": c.get("description"),
                "null_meaning": c.get("null_meaning"),
            }
        )
    return out


def add_label_records(
    records: list[dict[str, Any]], schema: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Add the joined name columns to a dataset's column dictionary.

    Driven by the schema's ``foreign_keys[].attribute_columns_added``, the
    same list :func:`relocate_labels` places in the rows. Each name column
    goes right after its code, with its description and nullability from the
    lookup table's schema (one cached request per lookup table).
    """
    out = list(records)
    for fk in schema.get("foreign_keys") or []:
        present = {r["column"] for r in out}
        added = [str(a) for a in fk.get("attribute_columns_added") or [] if a not in present]
        if not added:
            continue
        target_cols = lookup_schema(str(fk.get("target_object"))).get("columns") or []
        target = {c.get("name"): c for c in target_cols}
        rows = []
        for a in added:
            col = target.get(a) or {}
            rows.append(
                {
                    "column": a,
                    "label": None,
                    "type": "string",
                    "role": "label",
                    "label_of": fk.get("column"),
                    "unit": None,
                    "is_key_metric": False,
                    "metric_component": None,
                    "nullable": col.get("nullable"),
                    "valid_values": list(col.get("valid_values") or []),
                    "description": col.get("description")
                    or f"Joined from the {fk.get('target_object')} lookup table.",
                    "null_meaning": None,
                }
            )
        names = [r["column"] for r in out]
        at = names.index(fk["column"]) + 1 if fk.get("column") in names else len(out)
        out = out[:at] + rows + out[at:]
    return out


def _columns_table(records: Sequence[Mapping[str, Any]]) -> pa.Table:
    table = records_to_table(records, fields=COLUMN_FIELDS, list_cols=("valid_values",))
    return apply_schema_types(table, COLUMN_TYPES)


def _filters_table(schema: Mapping[str, Any]) -> pa.Table:
    """The filters table of a dataset schema."""
    table = records_to_table(
        schema.get("filters") or [], fields=FILTER_FIELDS, list_cols=("values",)
    )
    return apply_schema_types(table, FILTER_TYPES)


def _lookup_filters_table(schema: Mapping[str, Any]) -> pa.Table:
    """The filters table of a lookup-table schema (plus the ``q`` search)."""
    key = _strs(schema.get("primary_key"))
    col_type = {c.get("name"): c.get("type") or "string" for c in schema.get("columns") or []}
    records = []
    for f in schema.get("filters") or []:
        param = f.get("param")
        if param in key:
            kind = "key"
        elif col_type.get(param) == "boolean":
            kind = "boolean"
        elif f.get("values"):
            kind = "enum"
        else:
            kind = "foreign_key"
        records.append(
            {
                "param": param,
                "kind": kind,
                "values": list(f.get("values") or []),
                "multi_value": f.get("multi_value") is True,
                "has_total": None,
                "total_value": None,
                "requires_single_value": False,
                "nullable": None,
            }
        )
    search = schema.get("search") or {}
    if search.get("param") is not None:
        records.append(
            {
                "param": search["param"],
                "kind": "search",
                "values": [],
                "multi_value": False,
                "has_total": None,
                "total_value": None,
                "requires_single_value": False,
                "nullable": None,
            }
        )
    table = records_to_table(records, fields=FILTER_FIELDS, list_cols=("values",))
    return apply_schema_types(table, FILTER_TYPES)


def _geometry_filters_table(schema: Mapping[str, Any]) -> pa.Table:
    """The filters table of a geometry schema (the API gives a name -> text map)."""
    filters = schema.get("filters") or {}
    enums = {f.get("name"): list(f.get("enum") or []) for f in schema.get("fields") or []}
    records = []
    for param, spec in filters.items():
        if param in ("format", "resolution"):
            kind = "option"
        elif param == "year":
            kind = "year"
        elif param == "grade":
            kind = "grade"
        elif param.endswith("_code"):
            kind = "foreign_key"
        else:
            kind = "categorical"
        values = list(spec) if isinstance(spec, list) else enums.get(param, [])
        records.append(
            {
                "param": param,
                "kind": kind,
                "values": values,
                "multi_value": isinstance(spec, str) and "comma list" in spec,
                "has_total": None,
                "total_value": None,
                "requires_single_value": False,
                "nullable": None,
            }
        )
    table = records_to_table(records, fields=FILTER_FIELDS, list_cols=("values",))
    return apply_schema_types(table, FILTER_TYPES)


def _as_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [str(v)]


def _mapping_of_lists(x: Any) -> dict[str, list[str]] | None:
    if not isinstance(x, dict):
        return None
    return {str(k): _as_str_list(v) for k, v in x.items()}


def _notes(schema: Mapping[str, Any], backend: str) -> dict[str, Any]:
    """The contract declarations present in a dataset schema."""

    def table(x: Any, list_cols: Sequence[str] = ()) -> Any:
        if not x:
            return None
        return to_frame(records_to_table(list(x), list_cols=list_cols), backend)

    def one_row(x: Any) -> Any:
        if not x:
            return None
        return to_frame(records_to_table([x]), backend)

    notes: dict[str, Any] = {}
    for key in ("limitations", "year_meaning"):
        value = schema.get(key)
        if isinstance(value, str) and value:
            notes[key] = value
    if schema.get("null_semantics"):
        notes["null_semantics"] = dict(schema["null_semantics"])
    entries = {
        "series_breaks": table(schema.get("series_breaks"), ["metrics"]),
        "non_additive": table(
            schema.get("non_additive"),
            [
                c
                for c in ("metrics", "values", "with")
                if any(c in e for e in schema.get("non_additive") or [])
            ],
        ),
        "partitions": table(schema.get("partitions")),
        "pooled_rates": table(schema.get("pooled_rates")),
        "year_window": one_row(schema.get("year_window")),
    }
    implications = schema.get("value_implications") or []
    if implications:
        records = [
            {
                "when": _mapping_of_lists(v.get("when")),
                "implies": _mapping_of_lists(v.get("implies")),
                "excludes": _mapping_of_lists(v.get("excludes")),
                "reason": v.get("reason"),
            }
            for v in implications
        ]
        entries["value_implications"] = to_frame(records_to_table(records), backend)
    entries["pooled_min_count"] = one_row(schema.get("pooled_min_count"))
    order = (
        "series_breaks",
        "non_additive",
        "partitions",
        "pooled_rates",
        "year_window",
        "value_implications",
        "pooled_min_count",
    )
    for key in order:
        if entries.get(key) is not None:
            notes[key] = entries[key]
    return notes


# Printing --------------------------------------------------------------------


def _rule(text: str, width: int = 80) -> str:
    lead = f"-- {text} "
    return lead + "-" * max(2, width - len(lead))


def _year_span(years: Sequence[int]) -> str:
    if not years:
        return "none listed"
    if len(years) == 1:
        return str(years[0])
    return f"{min(years)}-{max(years)}"


def _lines_table(d: Description) -> list[str]:
    gaps = d.year_gaps
    details = [f"{lv} (default)" if lv == d.default_detail else lv for lv in d.detail_levels]
    lines = [_rule(f"{d.title} ({d.name})")]
    if isinstance(d.summary, str):
        lines.append(d.summary)
    lines.append("")
    lines.append(f"Source: {d.source or 'unknown'}")
    no_data = f" (no data for {', '.join(str(g) for g in gaps)})" if gaps else ""
    lines.append(f"Years: {_year_span(d.years)}{no_data}")
    lines.append(f"Detail levels: {', '.join(details)}")
    lines.append(f"Grain: {', '.join(d.grain)}")
    if isinstance(d.key_metric, str):
        lines.append(f"Key metric: {d.key_metric}")
    if d._single:
        lines.append(
            f"Pick one value of: {', '.join(d._single)} (no total; don't mix values in one summary)"
        )
    joined = ""
    if d._n_label:
        joined = f", plus {d._n_label} joined name column{'s' if d._n_label > 1 else ''}"
    n_filters = len(d._filter_params)
    lines.append(f"Columns: {d._n_own}{joined} (see .columns); filters: {n_filters} (see .filters)")
    lines.extend(_notes_lines(d.raw))
    return lines


def _lines_lookup(d: Description) -> list[str]:
    lines = [_rule(f"Lookup table: {d.name}")]
    if isinstance(d.description, str):
        lines.append(d.description)
    lines.append("")
    lines.append(f"Primary key: {' + '.join(d.primary_key)}")
    lines.append(f"Columns: {', '.join(d._column_names)}")
    lines.append(f"Filters: {', '.join(d._filter_params)}")
    if d.search_columns:
        lines.append(f"Text search (q) over: {', '.join(d.search_columns)}")
    lines.append(f"Get the rows with gcd.dimension({d.name!r}).")
    return lines


def _lines_geometry(d: Description) -> list[str]:
    notes = d.notes
    lines = [_rule(f"Geometry dataset: {d.name}")]
    if isinstance(d.description, str):
        lines.append(d.description)
    lines.append("")
    if isinstance(d.source, str):
        lines.append(f"Source: {d.source}")
    if isinstance(d.crs, str):
        lines.append(f"CRS: {d.crs}")
    if d.grain:
        lines.append(f"Grain: {', '.join(d.grain)}")
    lines.append(f"Fields: {d._n_own} (see .columns); filters: {', '.join(d._filter_params)}")
    if notes:
        lines.extend(["", _rule("Notes")])
    if isinstance(notes.get("limitations"), str):
        lines.append(f"* Limitations: {notes['limitations']}")
    if isinstance(notes.get("assignment_note"), str):
        lines.append(f"* {notes['assignment_note']}")
    if isinstance(notes.get("note"), str):
        lines.append(f"* {notes['note']}")
    return lines


def _notes_lines(schema: Mapping[str, Any]) -> list[str]:
    """Bullet lines for the contract declarations."""
    out: list[str] = []
    ns = schema.get("null_semantics") or {}
    if ns.get("suppressed_to_null") is True:
        since = ns.get("zero_is_real_from_year")
        if ns.get("zero_is_real") is True:
            zero = "zeros are real"
        elif since is not None:
            zero = f"zeros are real from {since} on"
        else:
            zero = "a zero may be suppressed too"
        out.append(f"* Missing values: missing means suppressed (small counts), not zero; {zero}.")
    for key, label in (("limitations", "Limitations"), ("year_meaning", "Year meaning")):
        value = schema.get(key)
        if isinstance(value, str) and value:
            out.append(f"* {label}: {value}")
    for sb in schema.get("series_breaks") or []:
        out.append(f"* Series break in {sb.get('year')}: {sb.get('reason')}")
    for na in schema.get("non_additive") or []:
        out.append(f"* Not additive ({na.get('column')}): {na.get('reason')}")
    for pt in schema.get("partitions") or []:
        out.append(f"* Partition ({pt.get('column')}): {pt.get('reason')}")
    for pr in schema.get("pooled_rates") or []:
        scale = pr.get("scale")
        suffix = "" if scale in (None, 1) else f" x {scale}"
        out.append(
            f"* Pooled rate: {pr.get('column')} = sum({pr.get('numerator')}) / "
            f"sum({pr.get('denominator')}){suffix}"
        )
    yw = schema.get("year_window")
    if yw:
        overlap = (
            " (windows overlap: not an annual series)" if yw.get("overlapping") is True else ""
        )
        out.append(
            f"* Year window: each figure pools {yw.get('years')} years, named by the "
            f"window's end year{overlap}."
        )
    for vi in schema.get("value_implications") or []:
        out.append(f"* Value implication: {vi.get('reason')}")
    pm = schema.get("pooled_min_count")
    if pm:
        out.append(f"* Pooled minimum count ({pm.get('count')}): {pm.get('reason')}")
    if not out:
        return []
    return ["", _rule("Notes"), *out]
