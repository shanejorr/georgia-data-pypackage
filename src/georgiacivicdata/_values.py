"""Get data: :func:`values`, the category combinations a filter covers."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, overload

import pandas as pd

from ._api import get_json
from ._frames import Frame, records_to_table, to_frame
from ._options import resolve_backend
from ._params import (
    as_names,
    check_query_args,
    dataset_query,
    encode_filters,
    encode_years,
)
from ._places import resolve_places
from ._schema import apply_schema_types, check_name_arg, row_types, schema_types, table_schema

if TYPE_CHECKING:
    import polars as pl


@overload
def values(
    name: str,
    columns: str | list[str],
    *,
    year: int | Sequence[int] | None = ...,
    detail: str | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    backend: Literal["pandas"],
    **filters: Any,
) -> pd.DataFrame: ...
@overload
def values(
    name: str,
    columns: str | list[str],
    *,
    year: int | Sequence[int] | None = ...,
    detail: str | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    backend: Literal["polars"],
    **filters: Any,
) -> pl.DataFrame: ...
@overload
def values(
    name: str,
    columns: str | list[str],
    *,
    year: int | Sequence[int] | None = ...,
    detail: str | None = ...,
    district: str | list[str] | None = ...,
    school: str | list[str] | None = ...,
    county: str | list[str] | None = ...,
    backend: None = ...,
    **filters: Any,
) -> Frame: ...
def values(
    name: str,
    columns: str | list[str],
    *,
    year: int | Sequence[int] | None = None,
    detail: str | None = None,
    district: str | list[str] | None = None,
    school: str | list[str] | None = None,
    county: str | list[str] | None = None,
    backend: Literal["pandas", "polars"] | None = None,
    **filters: Any,
) -> Frame:
    """List the category combinations a filter covers.

    Which combinations of category values exist, and how many rows each has,
    under the same filters as :func:`rows`. It answers "which subjects exist
    in 2016 at district level?" or "which demographic groups does this county
    have rows for?" without downloading the rows. The schema's
    ``valid_values`` list every value a column has ever used; ``values()``
    lists what exists **for this filter**, which is what you need when a
    filter returns zero rows.

    The API returns at most 500 combinations; the function warns when that
    cap is reached.

    Parameters
    ----------
    name : str
        The dataset's name.
    columns : str or list of str
        One or more categorical columns (or ``"demographic"``), such as
        ``"subject"`` or ``["subject", "grade_cluster"]``.
    year, detail, district, school, county :
        Exactly as in :func:`rows`.
    backend : {"pandas", "polars"}, optional
        The kind of data frame to return. Default: the ``backend`` option.
    **filters
        Named filters, exactly as in :func:`rows`.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        Most rows first, one column per requested column (typed from the
        schema; missing where the column is empty for those rows) and
        ``n_rows`` (integer), the number of rows with that combination.

    See Also
    --------
    rows : the rows themselves.
    describe : every filter and its allowed values.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.values(
    ...     "ccrpi_content_mastery", "subject", year=2016, detail="districts"
    ... )  # doctest: +SKIP
    >>> gcd.values(
    ...     "graduation_rate_4_year_cohort", "demographic",
    ...     district="Fulton County", year=2024,
    ... )  # doctest: +SKIP
    """
    check_name_arg(name, "name")
    resolve_backend(backend)
    columns_list = as_names(columns, "columns", allow_none=False)
    assert columns_list is not None
    check_query_args(detail, None, None)
    encoded = encode_filters(filters)
    years = encode_years(year)
    schema = table_schema(name, "values")
    places = resolve_places(
        district,
        school,
        county,
        filters=encoded,
        columns=list(schema_types(schema)),
        target=f'the dataset "{name}"',
    )
    query = dataset_query(encoded, years, detail, places, columns=columns_list)
    body = get_json(["datasets", name, "values"], query)
    fields = [str(c) for c in body.get("columns") or columns_list] + ["count"]
    table = records_to_table(body.get("data") or [], fields=fields)
    types = row_types(schema)
    wanted = {c: types[c] for c in fields if c in types}
    wanted["count"] = "integer"
    table = apply_schema_types(table, wanted)
    table = table.rename_columns(["n_rows" if c == "count" else c for c in table.column_names])
    if body.get("truncated") is True:
        total = body.get("total_combinations")
        of = f" of {total}" if total is not None else ""
        warnings.warn(
            f"Only the {table.num_rows} most common combinations are shown (the API "
            f"returns at most 500{of}). Add filters to narrow them.",
            UserWarning,
            stacklevel=2,
        )
    return to_frame(table, backend)
