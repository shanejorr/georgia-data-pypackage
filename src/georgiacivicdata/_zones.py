"""School attendance zones and district boundaries."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, overload

import pandas as pd
import pyarrow as pa

from ._api import build_url, perform
from ._frames import Frame, attach, records_to_table, to_frame, to_pandas
from ._options import resolve_backend
from ._params import _union, as_names, check_flag, format_number
from ._places import resolve_places
from ._schema import apply_schema_types, dataset_schema, order_columns, schema_types, select

if TYPE_CHECKING:
    import geopandas as gpd
    import polars as pl

ZONE_LEVELS = ("elementary", "middle", "high")
"""The zone levels, in order."""

GRADE_CODES = ("pk", "k", *(f"{g:02d}" for g in range(1, 13)))
"""Grades as the API spells them, in order."""

ZONE_COLUMNS = (
    "year",
    "district_code",
    "district_name",
    "school_code",
    "school_name",
    "zone_level",
    "grade_low",
    "grade_high",
    "method",
    "accuracy_class",
    "currency_status",
    "boundary_vintage",
    "source_url",
    "retrieved_on",
    "area_sq_mi",
    "bbox_xmin",
    "bbox_ymin",
    "bbox_xmax",
    "bbox_ymax",
    "source_school_name",
    "positional_rmse_m",
    "currency_note",
    "source_publisher",
    "nces_school_id",
    "district_census_id",
    "nces_lea_id",
)
BOUNDARY_COLUMNS = (
    "district_code",
    "district_name",
    "boundary_type",
    "district_census_id",
    "nces_lea_id",
    "grade_low",
    "grade_high",
    "tiger_geoid",
    "tiger_name",
    "tiger_vintage",
    "land_area_sq_mi",
    "area_sq_mi",
    "bbox_xmin",
    "bbox_ymin",
    "bbox_xmax",
    "bbox_ymax",
)
STATUS_COLUMNS = (
    "year",
    "district_code",
    "district_name",
    "school_code",
    "school_name",
    "zone_status",
    "zone_levels",
    "no_zone_category",
    "reason",
)
COVERAGE_COLUMNS = (
    "year",
    "district_code",
    "district_name",
    "tier",
    "status",
    "zone_level",
    "level_status",
    "pct_land_area",
    "pct_population",
    "zone_count",
    "methods",
    "accuracy_classes",
    "reason",
    "levels_covered",
    "currency_statuses",
    "best_lead",
    "extension_note",
    "served_elsewhere",
)


def normalize_grade(grade: Any) -> str | None:
    """Normalize one grade: ``"5"`` -> ``"05"``, ``"K"`` -> ``"k"``, ``"PK"`` /
    ``"Pre-K"`` -> ``"pk"``."""
    if grade is None:
        return None
    if isinstance(grade, int) and not isinstance(grade, bool):
        grade = str(grade)
    if not isinstance(grade, str):
        raise TypeError("`grade` must be one grade, such as 'k', '05' or 9.")
    g = re.sub(r"[\s-]", "", grade.lower())
    g = {"kindergarten": "k", "kk": "k", "prek": "pk", "prekindergarten": "pk"}.get(g, g)
    if g.isdigit():
        g = f"{int(g):02d}"
    if g not in GRADE_CODES:
        valid = ", ".join(repr(c) for c in GRADE_CODES)
        raise ValueError(f"`grade` must be one of {valid} ('5' and 'K' are accepted too).")
    return g


def check_year1(year: Any) -> str | None:
    """A single year argument."""
    if year is None:
        return None
    if isinstance(year, bool) or not isinstance(year, (int, float)) or not float(year).is_integer():
        raise TypeError("`year` must be a single year, such as 2027 (the 2026-27 school year).")
    return format_number(year)


def _check_geometry(geometry: Any, backend: str | None) -> bool:
    """geopandas is needed for geometry, which is always a GeoDataFrame."""
    check_flag(geometry, "geometry")
    if geometry:
        if backend == "polars":
            raise ValueError(
                "Geometry comes back as a geopandas GeoDataFrame, which has no Polars "
                "form. Use geometry=False for a Polars data frame of the attributes."
            )
        import_geopandas()
    elif backend is not None:
        resolve_backend(backend)
    return bool(geometry)


def import_geopandas() -> Any:
    try:
        import geopandas
        import shapely  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Returning geometry needs the 'geopandas' package. Install it with "
            "`pip install georgiacivicdata[geo]`, or use geometry=False."
        ) from exc
    return geopandas


def _fetch_geometry(
    path: Sequence[str], query: Mapping[str, list[str]], geometry: bool
) -> tuple[list[dict[str, Any]], list[Any] | None, dict[str, Any]]:
    """Fetch a geometry route as GeoJSON features or JSON records.

    Returns the attribute records, the GeoJSON geometries (``None`` for
    JSON) and the parsed body.
    """
    q = dict(query)
    q["format"] = ["geojson" if geometry else "json"]
    body = perform("GET", build_url(list(path), q), timeout=600).json()
    if geometry:
        features = body.get("features") or []
        records = [dict(f.get("properties") or {}) for f in features]
        return records, [f.get("geometry") for f in features], body
    return list(body.get("data") or []), None, body


def _keep_pairs(
    records: list[dict[str, Any]], geoms: list[Any] | None, schools: list[tuple[str, str]] | None
) -> tuple[list[dict[str, Any]], list[Any] | None]:
    """Keep only the (district, school) pairs a school name resolved to."""
    if schools is None:
        return records, geoms
    wanted = set(schools)
    keep = [
        i for i, r in enumerate(records) if (r.get("district_code"), r.get("school_code")) in wanted
    ]
    return [records[i] for i in keep], ([geoms[i] for i in keep] if geoms is not None else None)


def _geometry_codes(
    district_code: Any, school_code: Any, district: Any, school: Any, columns: Sequence[str]
) -> tuple[list[str], list[str], list[tuple[str, str]] | None]:
    """Codes from code and name arguments, for routes that take code lists."""
    dcodes = as_names(district_code, "district_code")
    scodes = as_names(school_code, "school_code")
    filters = {
        k: v for k, v in (("district_code", dcodes), ("school_code", scodes)) if v is not None
    }
    places = resolve_places(district, school, None, filters=filters, columns=list(columns))
    schools = places.schools
    return (
        _union(dcodes, places.district_code, [d for d, _ in schools or []]),
        _union(scodes, [s for _, s in schools or []]),
        schools,
    )


def _finish(
    table: pa.Table,
    geoms: list[Any] | None,
    backend: str | None,
    info: dict[str, Any] | None,
) -> Any:
    """A GeoDataFrame (WGS 84) when there are geometries, else a data frame."""
    if geoms is None:
        return to_frame(table, backend, info=info)
    gpd = import_geopandas()
    from shapely.geometry import shape

    df = to_pandas(table)
    shapes = [shape(g) if g else None for g in geoms]
    out = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries(shapes, index=df.index, crs="EPSG:4326"))
    if info is not None:
        attach(out, info)
    return out


@overload
def school_zones(
    district_code: str | list[str] | None = ...,
    school_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    zone_level: str | list[str] | None = ...,
    grade: str | int | None = ...,
    year: int | None = ...,
    resolution: Literal["display", "full"] = ...,
    *,
    geometry: Literal[True] = ...,
    backend: Literal["pandas"] | None = ...,
) -> gpd.GeoDataFrame: ...
@overload
def school_zones(
    district_code: str | list[str] | None = ...,
    school_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    zone_level: str | list[str] | None = ...,
    grade: str | int | None = ...,
    year: int | None = ...,
    resolution: Literal["display", "full"] = ...,
    *,
    geometry: Literal[False],
    backend: Literal["pandas", "polars"] | None = ...,
) -> Frame: ...
def school_zones(
    district_code: str | list[str] | None = None,
    school_code: str | list[str] | None = None,
    district: str | list[str] | None = None,
    school: str | list[str] | None = None,
    zone_level: str | list[str] | None = None,
    grade: str | int | None = None,
    year: int | None = None,
    resolution: Literal["display", "full"] = "display",
    *,
    geometry: bool = True,
    backend: Literal["pandas", "polars"] | None = None,
) -> Any:
    """Get school attendance zones.

    Attendance-zone polygons: the areas that assign a home to its zoned
    elementary, middle and high school, one polygon per school, level and
    grade run, for the current school year.

    **Zones differ in precision.** Some are the district's official GIS
    layers; others are digitized from PDF maps, rebuilt from street lists,
    or are the whole district outline (districts with one school per grade).
    Read ``method`` and ``accuracy_class`` before treating zones as equally
    exact, and see :func:`school_zone_coverage` for how completely each
    district was collected. A zone is the default assignment, not an
    official enrollment determination: confirm with the district.

    **A statewide pull is large**, especially at ``resolution="full"``.
    Filter to a district and keep the ``"display"`` default for maps.

    Parameters
    ----------
    district_code, school_code : str or list of str, optional
        Codes.
    district, school : str or list of str, optional
        Names, matched to codes as in :func:`rows`. A school name found in
        more than one district needs ``district`` too.
    zone_level : str or list of str, optional
        ``"elementary"``, ``"middle"`` and/or ``"high"``. Default: all.
    grade : str or int, optional
        One grade: keep zones serving it (``"pk"``, ``"k"``, ``"01"`` to
        ``"12"``; ``"5"``, ``5`` and ``"K"`` are accepted). Default: all.
    year : int, optional
        The zones' school year as its ending year (2027 is 2026-27).
        Default: the current zones.
    resolution : {"display", "full"}, default "display"
        ``"display"``: simplified polygons for maps, much smaller;
        ``"full"``: the source polygons the point lookup uses.
    geometry : bool, default True
        ``True`` returns a geopandas ``GeoDataFrame`` (needs the ``geo``
        extra: ``pip install georgiacivicdata[geo]``); ``False`` returns the
        attributes as a plain data frame.
    backend : {"pandas", "polars"}, optional
        With ``geometry=False``, the kind of data frame to return (default:
        the ``backend`` option). Geometry is always a ``GeoDataFrame``.

    Returns
    -------
    geopandas.GeoDataFrame or DataFrame
        One row per zone, with columns ``year`` (integer), ``district_code``,
        ``district_name``, ``school_code``, ``school_name``, ``zone_level``,
        ``grade_low``, ``grade_high`` (``"pk"``, ``"k"``, ``"01"`` ...
        ``"12"``), ``method`` (how the zone was built), ``accuracy_class``,
        ``currency_status``, ``boundary_vintage``, ``source_url``,
        ``retrieved_on`` (date), ``area_sq_mi``, the bounding box
        (``bbox_xmin``, ``bbox_ymin``, ``bbox_xmax``, ``bbox_ymax``),
        ``source_school_name`` (the name as the district's map spells it),
        then ``positional_rmse_m``, ``currency_note``, ``source_publisher``,
        ``nces_school_id``, ``district_census_id``, ``nces_lea_id`` and the
        ``geometry`` (WGS 84). The API's disclaimer is ``meta(x)["note"]``.

    See Also
    --------
    locate : the zones a point falls in.
    school_zone_status : schools without a zone.
    describe : with ``"school_attendance_zones"``, every field.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> zones = gcd.school_zones(
    ...     district="Atlanta Public Schools", zone_level="high"
    ... )  # doctest: +SKIP
    >>> zones.plot(column="school_name")  # doctest: +SKIP
    >>> gcd.school_zones(district_code="630", geometry=False)  # doctest: +SKIP
    """
    if resolution not in ("display", "full"):
        raise ValueError("`resolution` must be 'display' or 'full'.")
    geometry = _check_geometry(geometry, backend)
    levels = as_names(zone_level, "zone_level")
    g = normalize_grade(grade)
    y = check_year1(year)
    dcodes, scodes, schools = _geometry_codes(
        district_code, school_code, district, school, ["district_code", "school_code"]
    )
    query: dict[str, list[str]] = {}
    for name, value in (
        ("district_code", dcodes or None),
        ("school_code", scodes or None),
        ("zone_level", levels),
        ("grade", [g] if g else None),
        ("year", [y] if y else None),
        ("resolution", [resolution]),
    ):
        if value:
            query[name] = list(value)
    schema = dataset_schema("school_attendance_zones")
    records, geoms, body = _fetch_geometry(
        ["datasets", "school_attendance_zones", "rows"], query, geometry
    )
    records, geoms = _keep_pairs(records, geoms, schools)
    table = apply_schema_types(records_to_table(records), schema_types(schema))
    if table.num_columns == 0:
        table = apply_schema_types(
            records_to_table([], fields=list(ZONE_COLUMNS)), schema_types(schema)
        )
    table = select(table, order_columns(table.column_names, ZONE_COLUMNS))
    info = {"note": body.get("note") or schema.get("note")}
    return _finish(table, geoms, backend, info)


@overload
def district_boundaries(
    district_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    *,
    geometry: Literal[True] = ...,
    backend: Literal["pandas"] | None = ...,
) -> gpd.GeoDataFrame: ...
@overload
def district_boundaries(
    district_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    *,
    geometry: Literal[False],
    backend: Literal["pandas", "polars"] | None = ...,
) -> Frame: ...
def district_boundaries(
    district_code: str | list[str] | None = None,
    district: str | list[str] | None = None,
    *,
    geometry: bool = True,
    backend: Literal["pandas", "polars"] | None = None,
) -> Any:
    """Get school district boundaries.

    The Census TIGER/Line outlines of Georgia's school districts, keyed to
    district codes: unified districts, the secondary-only pieces some
    districts serve (Fort Benning grades 9-12), and the Department of
    Defense districts (which have no district code).

    Parameters
    ----------
    district_code : str or list of str, optional
        District codes. Default: every district.
    district : str or list of str, optional
        District names, matched to codes as in :func:`rows`.
    geometry : bool, default True
        ``True`` returns a geopandas ``GeoDataFrame``; ``False`` returns the
        attributes as a plain data frame.
    backend : {"pandas", "polars"}, optional
        With ``geometry=False``, the kind of data frame to return.

    Returns
    -------
    geopandas.GeoDataFrame or DataFrame
        One row per district piece, with columns ``district_code``,
        ``district_name`` (for Department of Defense districts, the Census
        name), ``boundary_type`` (``"unified"``, ``"secondary_extension"`` or
        ``"dodea"``), ``district_census_id``, ``nces_lea_id``, ``grade_low``,
        ``grade_high``, ``tiger_geoid``, ``tiger_name``, ``tiger_vintage``,
        ``land_area_sq_mi``, ``area_sq_mi``, the bounding box and the
        ``geometry`` (WGS 84).

    See Also
    --------
    school_zones : the zones inside each district.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.district_boundaries(district="Clay County")  # doctest: +SKIP
    >>> gcd.district_boundaries(geometry=False)  # doctest: +SKIP
    """
    geometry = _check_geometry(geometry, backend)
    dcodes, _, _ = _geometry_codes(district_code, None, district, None, ["district_code"])
    query = {"district_code": dcodes} if dcodes else {}
    records, geoms, _ = _fetch_geometry(
        ["datasets", "school_district_boundaries", "rows"], query, geometry
    )
    for r in records:
        if r.get("district_name") is None and r.get("tiger_name") is not None:
            r["district_name"] = r["tiger_name"]
    code_cols = ("district_code", "district_name", "district_census_id", "nces_lea_id")
    types = dict.fromkeys(code_cols, "string")
    table = apply_schema_types(records_to_table(records), types)
    if table.num_columns == 0:
        table = apply_schema_types(records_to_table([], fields=list(BOUNDARY_COLUMNS)), types)
    table = select(table, order_columns(table.column_names, BOUNDARY_COLUMNS))
    return _finish(table, geoms, backend, None)


@overload
def school_zone_status(
    district_code: str | list[str] | None = ...,
    school_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    zone_status: str | list[str] | None = ...,
    no_zone_category: str | list[str] | None = ...,
    *,
    backend: Literal["pandas"],
) -> pd.DataFrame: ...
@overload
def school_zone_status(
    district_code: str | list[str] | None = ...,
    school_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    zone_status: str | list[str] | None = ...,
    no_zone_category: str | list[str] | None = ...,
    *,
    backend: Literal["polars"],
) -> pl.DataFrame: ...
@overload
def school_zone_status(
    district_code: str | list[str] | None = ...,
    school_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    zone_status: str | list[str] | None = ...,
    no_zone_category: str | list[str] | None = ...,
    *,
    backend: None = ...,
) -> Frame: ...
def school_zone_status(
    district_code: str | list[str] | None = None,
    school_code: str | list[str] | None = None,
    district: str | list[str] | None = None,
    school: str | list[str] | None = None,
    zone_status: str | list[str] | None = None,
    no_zone_category: str | list[str] | None = None,
    *,
    backend: Literal["pandas", "polars"] | None = None,
) -> Frame:
    """Get each school's attendance-zone status.

    Whether each school of the standard districts has an attendance zone on
    the platform and, if not, why: a magnet or charter school with no zone, a
    district whose maps are not published yet, and so on. Answers "why
    doesn't this school have a zone?" without inferring it from a missing
    polygon.

    Parameters
    ----------
    district_code, school_code, district, school :
        As in :func:`school_zones`.
    zone_status : str or list of str, optional
        ``"zoned"``, ``"no_zone"`` and/or ``"not_yet_collected"``. Default:
        all.
    no_zone_category : str or list of str, optional
        Why a school has no zone (the API's categories, listed by
        :func:`describe` with ``"school_attendance_zones"``). Default: all.
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        One row per school, with columns ``year`` (integer),
        ``district_code``, ``district_name``, ``school_code``,
        ``school_name``, ``zone_status``, ``zone_levels`` (the levels it is
        zoned for, as one string), ``no_zone_category`` and ``reason``. The
        API's note on reading the table is ``meta(x)["note"]``.

    See Also
    --------
    school_zones : the zones.
    school_zone_coverage : each district's coverage.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.school_zone_status(district="Atlanta Public Schools")  # doctest: +SKIP
    >>> gcd.school_zone_status(zone_status="no_zone")  # doctest: +SKIP
    """
    resolve_backend(backend)
    statuses = as_names(zone_status, "zone_status")
    categories = as_names(no_zone_category, "no_zone_category")
    dcodes, scodes, schools = _geometry_codes(
        district_code, school_code, district, school, ["district_code", "school_code"]
    )
    query: dict[str, list[str]] = {}
    for name, value in (
        ("district_code", dcodes or None),
        ("school_code", scodes or None),
        ("zone_status", statuses),
        ("no_zone_category", categories),
    ):
        if value:
            query[name] = list(value)
    records, _, body = _fetch_geometry(
        ["datasets", "school_attendance_zones", "school_status"], query, False
    )
    records, _ = _keep_pairs(records, None, schools)
    fields = None if records else list(STATUS_COLUMNS)
    table = apply_schema_types(
        records_to_table(records, fields=fields),
        {"year": "integer", **{c: "string" for c in STATUS_COLUMNS if c != "year"}},
    )
    table = select(table, order_columns(table.column_names, STATUS_COLUMNS))
    return to_frame(table, backend, info={"note": body.get("note")})


@overload
def school_zone_coverage(
    district_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    *,
    geometry: Literal[False] = ...,
    backend: Literal["pandas", "polars"] | None = ...,
) -> Frame: ...
@overload
def school_zone_coverage(
    district_code: str | list[str] | None = ...,
    district: str | list[str] | None = ...,
    *,
    geometry: Literal[True],
    backend: Literal["pandas"] | None = ...,
) -> gpd.GeoDataFrame: ...
def school_zone_coverage(
    district_code: str | list[str] | None = None,
    district: str | list[str] | None = None,
    *,
    geometry: bool = False,
    backend: Literal["pandas", "polars"] | None = None,
) -> Any:
    """Get each district's attendance-zone coverage.

    How completely each standard district's attendance zones were collected,
    one row per district and zone level: the source tier, the status of each
    level, the share of the district's land and 2020 population the zones
    cover, how they were built, and the reason for anything short of
    complete.

    The API returns one row per district with a column per level
    (``level_status_elementary``, ``pct_population_middle``, ...); this
    function pivots those columns long. The district filter runs locally
    (the route takes no filters; the table has about 180 rows).

    Parameters
    ----------
    district_code, district :
        As in :func:`district_boundaries`.
    geometry : bool, default False
        ``False`` returns a data frame; ``True`` returns a ``GeoDataFrame``
        of the district outlines carrying the same fields.
    backend : {"pandas", "polars"}, optional
        With ``geometry=False``, the kind of data frame to return.

    Returns
    -------
    DataFrame or geopandas.GeoDataFrame
        One row per district and zone level, with columns ``year``
        (integer), ``district_code``, ``district_name``, ``tier`` (the source
        tier, A to E or N), ``status`` (the district's overall status),
        ``zone_level``, ``level_status`` (``"zoned"``,
        ``"one_school_per_grade"``, ``"partial"``, ``"not_available"``,
        ``"served_by_other_district"``), ``pct_land_area`` and
        ``pct_population`` (0-1, the share the level's zones cover),
        ``zone_count``, ``methods``, ``accuracy_classes``, ``reason``, then
        ``levels_covered``, ``currency_statuses``, ``best_lead``,
        ``extension_note`` and ``served_elsewhere`` (a list column of dicts:
        the other district's school serving that level, with
        ``district_code``, ``school_code`` and ``reason``).

    See Also
    --------
    school_zones : the zones.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.school_zone_coverage(district="Clay County")  # doctest: +SKIP
    >>> coverage = gcd.school_zone_coverage()  # doctest: +SKIP
    >>> coverage.groupby(["zone_level", "level_status"]).size()  # doctest: +SKIP
    """
    geometry = _check_geometry(geometry, backend)
    dcodes, _, _ = _geometry_codes(district_code, None, district, None, ["district_code"])
    records, geoms, body = _fetch_geometry(
        ["datasets", "school_attendance_zones", "coverage"], {}, geometry
    )
    if dcodes:
        keep = [i for i, r in enumerate(records) if r.get("district_code") in dcodes]
        records = [records[i] for i in keep]
        geoms = [geoms[i] for i in keep] if geoms is not None else None
    long_records, long_geoms = pivot_coverage(records, geoms)
    fields = list(COVERAGE_COLUMNS)
    extra = [k for r in long_records for k in r if k not in fields]
    for k in extra:
        if k not in fields:
            fields.append(k)
    table = records_to_table(long_records, fields=fields, list_cols=("served_elsewhere",))
    table = apply_schema_types(
        table,
        {
            "year": "integer",
            "zone_count": "integer",
            "pct_land_area": "number",
            "pct_population": "number",
        },
    )
    return _finish(table, long_geoms, backend, {"note": body.get("note")})


def pivot_coverage(
    records: list[dict[str, Any]], geoms: list[Any] | None
) -> tuple[list[dict[str, Any]], list[Any] | None]:
    """Pivot the per-level coverage columns long (one row per district and
    level), repeating each district's geometry."""
    pattern = re.compile(r"^(.+)_(" + "|".join(ZONE_LEVELS) + r")$")
    out: list[dict[str, Any]] = []
    out_geoms: list[Any] | None = [] if geoms is not None else None
    for i, record in enumerate(records):
        base: dict[str, Any] = {}
        per_level: dict[str, dict[str, Any]] = {lv: {} for lv in ZONE_LEVELS}
        served = record.get("served_elsewhere")
        for key, value in record.items():
            if key == "served_elsewhere":
                continue
            match = pattern.match(key)
            if match:
                per_level[match.group(2)][match.group(1)] = value
            else:
                base[key] = value
        for level in ZONE_LEVELS:
            row = {**base, "zone_level": level, **per_level[level]}
            row["served_elsewhere"] = served_for_level(served, level)
            out.append(row)
            if out_geoms is not None and geoms is not None:
                out_geoms.append(geoms[i])
    return out, out_geoms


def served_for_level(entries: Any, level: str) -> list[dict[str, Any]]:
    """The ``served_elsewhere`` entries for one level."""
    if isinstance(entries, str) and entries:
        entries = json.loads(entries)
    if not entries:
        return []
    return [
        {k: e.get(k) for k in ("district_code", "school_code", "reason")}
        for e in entries
        if isinstance(e, dict) and e.get("zone_level") == level
    ]
