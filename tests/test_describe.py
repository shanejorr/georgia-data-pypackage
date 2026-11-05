from __future__ import annotations

import pandas as pd
import pytest

import georgiacivicdata as gcd
from georgiacivicdata._describe import (
    Description,
    _describe_table,
    add_label_records,
    column_records,
)
from helpers import error_response, recorded, seed_meta, url

COLUMN_FIELDS = [
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
]
LABELS = [
    "district_name",
    "district_census_id",
    "district_type",
    "school_name",
    "demographic_label",
    "demographic_category",
]


def mock_grad_schemas(api, folder="desc"):
    api.get(url("datasets", "graduation_rate_4_year_cohort")).mock(
        return_value=recorded(f"m/{folder}/g/d/graduation_rate_4_year_cohort.json")
    )
    for dim in ("demographics", "districts", "schools"):
        api.get(url("dimensions", dim)).mock(return_value=recorded(f"m/desc/g/m/{dim}.json"))


def test_describe_summarizes_a_dataset(api, snapshot):
    mock_grad_schemas(api)
    d = gcd.describe("graduation_rate_4_year_cohort")
    cols = gcd.columns("graduation_rate_4_year_cohort")
    own = gcd.columns("graduation_rate_4_year_cohort", labels=False)
    assert isinstance(d, Description)
    assert d.kind == "table"
    assert all(isinstance(y, int) for y in d.years)
    assert d.key_metric == "graduation_rate"
    pd.testing.assert_frame_equal(d.columns, cols)
    assert list(d.filters.columns) == [
        "param",
        "kind",
        "values",
        "multi_value",
        "has_total",
        "total_value",
        "requires_single_value",
        "nullable",
    ]
    assert "district_type" in d.filters["param"].tolist()
    assert isinstance(d.notes["series_breaks"], pd.DataFrame)
    assert not {"sub_topic", "topic", "key"} & set(d.raw)
    assert d.format(width=80) == snapshot
    assert repr(d) == str(d)

    assert list(cols.columns) == COLUMN_FIELDS
    assert cols.loc[cols["is_key_metric"], "column"].tolist() == ["graduation_rate"]
    # The joined name columns sit right after their codes, as in rows()
    assert cols.loc[cols["role"] == "label", "column"].tolist() == LABELS
    assert own["column"].tolist() == [c for c in cols["column"] if c not in LABELS]
    assert own["label_of"].isna().all()
    names = cols["column"].tolist()
    for code, label in (
        ("district_code", "district_name"),
        ("school_code", "school_name"),
        ("demographic", "demographic_label"),
    ):
        assert names[names.index(code) + 1] == label
    assert cols.set_index("column").loc["demographic_category", "label_of"] == "demographic"
    assert set(cols.loc[cols["role"] == "label", "type"]) == {"string"}
    assert not cols.loc[cols["role"] == "label", "is_key_metric"].any()
    by_name = cols.set_index("column")
    assert by_name.loc["school_name", "description"]
    assert "race" in by_name.loc["demographic_category", "valid_values"]
    assert by_name.loc["num_cohort", "metric_component"] == "denominator"
    assert "all" in by_name.loc["demographic", "valid_values"]


def test_describe_with_polars(api):
    pl = pytest.importorskip("polars")
    mock_grad_schemas(api)
    d = gcd.describe("graduation_rate_4_year_cohort", backend="polars")
    assert isinstance(d.columns, pl.DataFrame)
    assert isinstance(d.filters, pl.DataFrame)
    assert isinstance(d.notes["series_breaks"], pl.DataFrame)
    cols = gcd.columns("graduation_rate_4_year_cohort", backend="polars")
    assert cols.schema["valid_values"] == pl.List(pl.String)


def test_label_columns_fall_back_to_a_plain_description():
    seed_meta(
        ["dimensions", "counties"],
        {"name": "counties", "columns": [{"name": "county_fips", "type": "string", "role": "key"}]},
    )
    schema = {
        "columns": [
            {"name": "year", "type": "integer", "role": "year"},
            {"name": "county_fips", "type": "string", "role": "fk_county"},
            {"name": "rate", "type": "number", "role": "metric"},
        ],
        "foreign_keys": [
            {
                "column": "county_fips",
                "target_object": "counties",
                "attribute_columns_added": ["county_name"],
            }
        ],
    }
    cols = add_label_records(column_records(schema, "table"), schema)
    assert [c["column"] for c in cols] == ["year", "county_fips", "county_name", "rate"]
    assert cols[2]["description"] == "Joined from the counties lookup table."
    assert cols[2]["nullable"] is None
    assert cols[2]["valid_values"] == []
    with pytest.raises(TypeError, match="`labels` must be True or False"):
        gcd.columns("infant_deaths", labels=None)


def test_describe_lists_columns_that_need_one_value(api, snapshot):
    mock_grad_schemas(api)
    api.get(url("datasets", "ccrpi_content_mastery")).mock(
        return_value=recorded("m/desc2/g/d/ccrpi_content_mastery.json")
    )
    d = gcd.describe("ccrpi_content_mastery")
    single = d.filters.loc[d.filters["requires_single_value"].fillna(False), "param"].tolist()
    assert "grade_cluster" in single
    assert d.format(width=80) == snapshot


def test_describe_and_columns_read_lookup_tables(api, snapshot):
    api.get(url("dimensions", "schools")).mock(return_value=recorded("m/descl/g/m/schools.json"))
    d = gcd.describe("schools")
    cols = gcd.columns("schools")
    assert d.kind == "lookup"
    assert d.primary_key == ["district_code", "school_code"]
    assert {"key", "enum", "boolean", "search"} <= set(d.filters["kind"])
    by_name = cols.set_index("column")
    assert by_name.loc["school_code", "role"] == "key"
    assert cols["label"].isna().all()
    assert not cols["is_key_metric"].any()
    assert by_name.loc["locale", "valid_values"] == ["city", "suburb", "town", "rural"]
    assert d.format(width=80) == snapshot


def test_describe_reads_geometry_datasets(api, snapshot):
    api.get(url("datasets", "school_attendance_zones")).mock(
        return_value=recorded("m/descg/g/d/school_attendance_zones.json")
    )
    d = gcd.describe("school_attendance_zones")
    assert d.kind == "geometry"
    by_name = d.columns.set_index("column")
    assert by_name.loc["retrieved_on", "type"] == "date"
    filters = d.filters.set_index("param")
    assert filters.loc["zone_level", "values"] == ["elementary", "middle", "high"]
    assert bool(filters.loc["district_code", "multi_value"]) is True
    assert isinstance(d.notes["assignment_note"], str)
    assert d.format(width=80) == snapshot


def test_every_declared_note_is_kept_and_printed(snapshot):
    seed_meta(["dimensions", "x"], {"columns": []})
    schema = {
        "name": "toy",
        "title": "Toy Data",
        "summary": "A toy.",
        "source": "Somewhere",
        "available_years": [2022, 2024],
        "year_gaps": [2023],
        "detail_levels": ["counties", "states"],
        "default_detail": "counties",
        "grain": ["year", "county_fips"],
        "key_metric": "rate",
        "columns": [{"name": "rate", "type": "number", "role": "metric"}],
        "filters": [
            {
                "param": "payer",
                "kind": "categorical",
                "values": ["a", "b"],
                "requires_single_value": True,
            }
        ],
        "limitations": "Small samples.",
        "year_meaning": "The year the survey ended.",
        "null_semantics": {"suppressed_to_null": True, "zero_is_real": False},
        "series_breaks": [{"year": 2024, "reason": "New method.", "metrics": ["rate"]}],
        "non_additive": [{"column": "race", "reason": "Groups overlap.", "values": ["a", "b"]}],
        "partitions": [{"column": "payer", "share": "share", "reason": "Shares add to 1."}],
        "pooled_rates": [
            {"column": "rate", "numerator": "events", "denominator": "pop", "scale": 1000}
        ],
        "year_window": {"years": 3, "overlapping": True},
        "value_implications": [
            {
                "when": {"born": ["pr"]},
                "implies": {"citizen": "native"},
                "reason": "Born in Puerto Rico implies native.",
            }
        ],
        "pooled_min_count": {"count": 20, "reason": "Under 20 events is withheld."},
    }
    d = _describe_table(schema, "pandas")
    assert list(d.notes) == [
        "limitations",
        "year_meaning",
        "null_semantics",
        "series_breaks",
        "non_additive",
        "partitions",
        "pooled_rates",
        "year_window",
        "value_implications",
        "pooled_min_count",
    ]
    assert d.notes["non_additive"]["values"].iloc[0] == ["a", "b"]
    assert d.notes["value_implications"]["implies"].iloc[0] == {"citizen": ["native"]}
    assert d.format(width=80) == snapshot
    assert d.format(width=30).splitlines()[1] == "A toy."


def test_contract_returns_the_contract_or_writes_its_yaml(api, tmp_path):
    api.get(
        url("datasets", "graduation_rate_4_year_cohort", "contract"), params={"format": "json"}
    ).mock(return_value=recorded("m/ctr/g/d/graduation_rate_4_year_cohort/contract-7315b4.json"))
    api.get(
        url("datasets", "graduation_rate_4_year_cohort", "contract"), params={"format": "yaml"}
    ).mock(return_value=recorded("m/ctr/g/d/graduation_rate_4_year_cohort/contract-4f8213.txt"))
    spec = gcd.contract("graduation_rate_4_year_cohort")
    assert spec["kind"] == "DataContract"
    assert spec["name"] == "graduation_rate_4_year_cohort"
    path = tmp_path / "contract.yaml"
    assert gcd.contract("graduation_rate_4_year_cohort", file=path) == path
    assert path.read_text().splitlines()[0].startswith("apiVersion:")


def test_contract_refuses_lookup_tables_and_geometry_without_a_contract(api):
    seed_meta(
        ["datasets", "school_district_boundaries"],
        {"name": "school_district_boundaries", "kind": "geometry"},
    )
    api.get(url("datasets", "school_district_boundaries", "contract")).mock(
        return_value=error_response(
            404, "TOPIC_NOT_FOUND", "No dataset 'school_district_boundaries'"
        )
    )
    api.get(url("datasets", "nope", "contract")).mock(
        return_value=error_response(
            404, "TOPIC_NOT_FOUND", "No dataset 'nope'", {"did_you_mean": ["employment"]}
        )
    )
    api.get(url("datasets", "nope")).mock(
        return_value=error_response(
            404, "TOPIC_NOT_FOUND", "No dataset 'nope'", {"did_you_mean": ["employment"]}
        )
    )
    with pytest.raises(gcd.GCDNotFoundError, match="No dataset 'nope'"):
        gcd.contract("nope", file="x.yaml")
    with pytest.raises(gcd.GCDError, match="Lookup tables have no contract route") as info:
        gcd.contract("counties")
    assert info.value.code == "NO_CONTRACT"
    with pytest.raises(
        gcd.GCDError, match="The geometry dataset 'school_district_boundaries' has no"
    ):
        gcd.contract("school_district_boundaries")
    with pytest.raises(TypeError, match="`file` must be a single path"):
        gcd.contract("x", file=1)
