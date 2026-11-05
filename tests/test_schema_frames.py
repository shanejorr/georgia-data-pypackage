from __future__ import annotations

import datetime as dt
import gc

import pandas as pd
import pyarrow as pa
import pytest

import georgiacivicdata as gcd
from georgiacivicdata import _frames
from georgiacivicdata._frames import attach, attached, make_array, records_to_table, to_frame
from georgiacivicdata._schema import (
    apply_schema_types,
    code_columns,
    drop_empty_codes,
    drop_internal,
    empty_typed,
    label_columns,
    move_after,
    order_columns,
    parse_utc,
    relocate_labels,
    resource_kind,
    row_types,
    schema_types,
    table_schema,
)
from helpers import seed_meta

SCHEMA = {
    "name": "toy",
    "columns": [
        {"name": "year", "type": "integer", "role": "year"},
        {"name": "district_code", "type": "string", "role": "fk_district"},
        {"name": "school_code", "type": "string", "role": "fk_school"},
        {"name": "demographic", "type": "string", "role": "fk_demographic"},
        {"name": "n", "type": "integer", "role": "metric"},
    ],
    "foreign_keys": [
        {"column": "district_code", "attribute_columns_added": ["district_name", "district_type"]},
        {"column": "school_code", "attribute_columns_added": ["school_name"]},
        {"column": "demographic", "attribute_columns_added": ["demographic_label"]},
    ],
}


def test_apply_schema_types_types_text_columns_from_the_schema():
    table = pa.table(
        {
            "year": ["2024", "2025"],
            "district_code": ["0103", None],
            "county_fips": pa.array([13121, 13089]),
            "count": ["10", "3000000000"],
            "rate": ["0.9375", ""],
            "flag": ["true", "FALSE"],
            "day": ["2026-10-02", None],
            "at": ["2026-10-29T20:17:55+00:00", None],
            "joined_name": pa.array([None, None], pa.null()),
        }
    )
    types = {
        "year": "integer",
        "district_code": "string",
        "county_fips": "string",
        "count": "integer",
        "rate": "number",
        "flag": "boolean",
        "day": "date",
        "at": "timestamp",
    }
    out = apply_schema_types(table, types).to_pydict()
    assert out["year"] == [2024, 2025]
    assert out["district_code"] == ["0103", None]
    assert out["county_fips"] == ["13121", "13089"]
    assert out["count"] == [10, 3000000000]
    assert out["rate"] == [0.9375, None]
    assert out["flag"] == [True, False]
    assert out["day"] == [dt.date(2026, 10, 2), None]
    assert out["at"][0] == dt.datetime(2026, 10, 29, 20, 17, 55, tzinfo=dt.timezone.utc)
    assert out["joined_name"] == [None, None]
    assert apply_schema_types(table, types).schema.field("joined_name").type == pa.string()


def test_integers_stay_integers_when_they_are_whole():
    def convert(values, t="integer"):
        return apply_schema_types(pa.table({"x": values}), {"x": t}).column("x")

    assert convert([1.0, 2.0, None]).type == pa.int64()
    assert convert([1.0, 2.5]).type == pa.float64()
    assert convert(["1", "2.5"]).type == pa.float64()
    assert convert(pa.array([True, False])).type == pa.int64()
    assert convert(pa.array([None, None], pa.null())).type == pa.int64()
    assert convert(["1", "x"]).to_pylist() == [1, None]
    assert convert([1.0, float("inf")]).type == pa.float64()


def test_numbers_booleans_dates_and_strings_from_other_types():
    def convert(values, t):
        return apply_schema_types(pa.table({"x": values}), {"x": t}).column("x").to_pylist()

    assert convert([1, 2], "number") == [1.0, 2.0]
    assert convert(["0.5", "bad", None], "number") == [0.5, None, None]
    assert convert([1, 0], "boolean") == [True, False]
    assert convert(["t", "f", "1", "0", "x", None], "boolean") == [
        True,
        False,
        True,
        False,
        None,
        None,
    ]
    assert convert(pa.array([None], pa.null()), "boolean") == [None]
    assert convert(["2026-01-02", "nope"], "date") == [dt.date(2026, 1, 2), None]
    assert convert(pa.array([True, False]), "string") == ["true", "false"]
    assert convert([1.0, 2.5], "string") == ["1", "2.5"]
    assert convert([1, 2], "string") == ["1", "2"]
    assert convert(["a"], "unknown") == ["a"]
    assert convert(pa.array([None], pa.null()), "unknown") == [None]


def test_parse_utc_reads_iso_timestamps_with_offsets():
    expected = dt.datetime(2026, 10, 29, 20, 17, 55, tzinfo=dt.timezone.utc)
    for text in (
        "2026-10-29T20:17:55+00:00",
        "2026-10-29T15:17:55-05:00",
        "2026-10-29T20:17:55Z",
        "2026-10-29 20:17:55",
    ):
        assert parse_utc(text) == expected
    assert parse_utc(None) is None
    assert parse_utc("") is None
    assert parse_utc("not a date") is None
    assert parse_utc(dt.datetime(2026, 10, 29, 20, 17, 55)) == expected


def test_label_columns_come_from_foreign_keys():
    assert label_columns(SCHEMA) == [
        "district_name",
        "district_type",
        "school_name",
        "demographic_label",
    ]
    types = row_types(SCHEMA)
    assert types["district_name"] == "string"
    assert types["n"] == "integer"
    assert code_columns(SCHEMA) == ["district_code", "school_code", "demographic"]


def test_relocate_labels_puts_each_label_after_its_code():
    cols = [
        "year",
        "district_code",
        "school_code",
        "demographic",
        "n",
        "district_name",
        "district_type",
        "school_name",
        "demographic_label",
    ]
    assert relocate_labels(cols, SCHEMA["foreign_keys"]) == [
        "year",
        "district_code",
        "district_name",
        "district_type",
        "school_code",
        "school_name",
        "demographic",
        "demographic_label",
        "n",
    ]
    assert relocate_labels(
        ["year", "district_code", "n", "district_name"], SCHEMA["foreign_keys"]
    ) == [
        "year",
        "district_code",
        "district_name",
        "n",
    ]


def test_move_after_and_order_columns():
    cols = ["a", "b", "c", "d"]
    assert move_after(cols, ["d"], "a") == ["a", "d", "b", "c"]
    assert move_after(cols, ["z"], "a") == cols
    assert move_after(cols, ["b"], "z") == cols
    assert order_columns(cols, ["c", "z", "a"]) == ["c", "a", "b", "d"]


def test_drop_empty_codes_drops_all_null_code_columns_only():
    table = pa.table(
        {
            "year": [2024, 2024],
            "district_code": ["660", None],
            "school_code": pa.array([None, None], pa.string()),
            "n": [None, 1],
        }
    )
    out = drop_empty_codes(table, code_columns(SCHEMA))
    assert out.column_names == ["year", "district_code", "n"]
    assert (
        drop_empty_codes(table.slice(0, 0), code_columns(SCHEMA)).column_names == table.column_names
    )


def test_drop_internal_removes_sub_topic_topic_and_key():
    x = {"name": "a", "sub_topic": "s", "topic": "t", "key": "k/s/t", "title": "T"}
    assert drop_internal(x) == {"name": "a", "title": "T"}
    assert drop_internal("x") == "x"


def test_empty_typed_builds_a_typed_zero_row_table():
    out = empty_typed(["year", "flag", "x"], {"year": "integer", "flag": "boolean"})
    assert out.num_rows == 0
    assert out.schema.field("year").type == pa.int64()
    assert out.schema.field("flag").type == pa.bool_()
    assert out.schema.field("x").type == pa.string()
    assert empty_typed([], {}).num_columns == 0


def test_schema_types_reads_columns_or_geometry_fields():
    assert schema_types({"fields": [{"name": "a", "type": "date"}, {"name": "b"}]}) == {
        "a": "date",
        "b": "string",
    }
    assert schema_types({}) == {}


def test_table_schema_points_lookup_tables_and_geometry_elsewhere():
    seed_meta(["datasets", "school_attendance_zones"], {"kind": "geometry"})
    seed_meta(["datasets", "school_district_boundaries"], {"kind": "geometry"})
    with pytest.raises(gcd.GCDError, match=r"'counties' is a lookup table") as info:
        table_schema("counties", "rows")
    assert info.value.code == "NOT_A_DATASET"
    assert "gcd.dimension('counties')" in str(info.value)
    with pytest.raises(gcd.GCDError, match=r"Use gcd.school_zones\(\) instead"):
        table_schema("school_attendance_zones", "rows")
    with pytest.raises(gcd.GCDError, match=r"Use gcd.district_boundaries\(\) instead"):
        table_schema("school_district_boundaries", "values")
    assert resource_kind("counties") == "lookup"
    assert resource_kind("school_attendance_zones") == "geometry"
    with pytest.raises(TypeError, match="single string"):
        table_schema("", "rows")


# Frames ----------------------------------------------------------------------


def test_records_to_table_simplifies_scalars_and_keeps_arrays_as_lists():
    records = [
        {"name": "a", "n": 1, "levels": ["x", "y"], "missing": None},
        {"name": "b", "n": None, "levels": [], "extra": True},
    ]
    out = records_to_table(records, list_cols=["levels"])
    assert out.column_names == ["name", "n", "levels", "missing", "extra"]
    assert out.column("name").to_pylist() == ["a", "b"]
    assert out.column("n").to_pylist() == [1, None]
    assert out.column("levels").to_pylist() == [["x", "y"], []]
    assert out.column("extra").to_pylist() == [None, True]


def test_records_to_table_fixes_fields_and_handles_no_records():
    out = records_to_table([{"a": 1}], fields=["a", "b"])
    assert out.column_names == ["a", "b"]
    assert out.column("b").to_pylist() == [None]
    empty = records_to_table([], fields=["a", "l"], list_cols=["l"])
    assert empty.num_rows == 0
    assert pa.types.is_list(empty.schema.field("l").type)
    assert records_to_table([]).num_columns == 0


def test_make_array_falls_back_to_text_for_mixed_values():
    assert make_array([1, "a"]).to_pylist() == ["1", "a"]
    assert make_array([True, 1]).type in (pa.string(), pa.int64(), pa.bool_())
    assert make_array([{"a": 1}, "x"]).to_pylist() == ['{"a": 1}', "x"]
    assert make_array([[1, "a"], None]).to_pylist() == [["1", "a"], []]
    assert make_array(["x", None], as_list=True).to_pylist() == [["x"], []]
    assert make_array([[], []]).type == pa.list_(pa.string())


def test_to_frame_gives_nullable_pandas_dtypes():
    table = pa.table(
        {
            "code": ["0103", None],
            "n": [1, None],
            "rate": [0.5, None],
            "flag": [True, None],
            "day": pa.array([dt.date(2026, 1, 2), None], pa.date32()),
            "levels": [["a"], None],
            "nothing": pa.array([None, None], pa.null()),
        }
    )
    df = to_frame(table, "pandas")
    assert str(df["code"].dtype) == "string"
    assert str(df["n"].dtype) == "Int64"
    assert df["rate"].dtype == "float64"
    assert str(df["flag"].dtype) == "boolean"
    assert str(df["day"].dtype).startswith("datetime64")
    assert df["levels"].tolist() == [["a"], []]
    assert str(df["nothing"].dtype) == "string"
    assert df["code"].iloc[0] == "0103"
    assert pd.isna(df["n"].iloc[1])


def test_to_frame_gives_polars():
    pl = pytest.importorskip("polars")
    table = pa.table({"code": ["0103"], "n": [1], "levels": [["a", "b"]]})
    df = to_frame(table, "polars")
    assert isinstance(df, pl.DataFrame)
    assert df.schema["code"] == pl.String
    assert df.schema["n"] == pl.Int64
    assert df["levels"].to_list() == [["a", "b"]]
    gcd.set_option("backend", "polars")
    assert isinstance(to_frame(table, None), pl.DataFrame)


def test_polars_backend_without_polars_explains_the_install(monkeypatch):
    def missing():
        raise ImportError("backend='polars' needs the 'polars' package.")

    monkeypatch.setattr(_frames, "import_polars", missing)
    with pytest.raises(ImportError, match="needs the 'polars' package"):
        to_frame(pa.table({"a": [1]}), "polars")


def test_import_polars_message(monkeypatch):
    import builtins

    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name == "polars":
            raise ImportError("no polars")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(ImportError, match=r"georgiacivicdata\[polars\]"):
        _frames.import_polars()


def test_metadata_is_attached_and_released():
    df = pd.DataFrame({"a": [1]})
    attach(df, {"dataset": "d"})
    assert attached(df) == {"dataset": "d"}
    assert df.attrs["gcd_meta"] == {"dataset": "d"}
    key = id(df)
    del df
    gc.collect()
    assert key not in _frames._REGISTRY
    copy = pd.DataFrame({"a": [1]})
    copy.attrs["gcd_meta"] = {"dataset": "e"}
    assert attached(copy) == {"dataset": "e"}
    assert attached(pd.DataFrame()) is None


def test_metadata_works_for_polars():
    pl = pytest.importorskip("polars")
    df = pl.DataFrame({"a": [1]})
    attach(df, {"dataset": "d"})
    assert attached(df) == {"dataset": "d"}
    assert attached(df.filter(pl.col("a") > 0)) is None
