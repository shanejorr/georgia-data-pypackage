from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd
import pytest

from georgiacivicdata._params import (
    Places,
    check_n_max,
    check_query_args,
    dataset_query,
    dataset_request,
    encode_filters,
    encode_values,
    encode_years,
    format_number,
)


def test_encode_values_writes_missing_booleans_numbers_and_dates_as_text():
    assert encode_values(["all", None], "x") == ["all", "__null__"]
    assert encode_values([True, False, None], "x") == ["true", "false", "__null__"]
    assert encode_values([0.9, 2024, 1e-7, 123456789012], "x") == [
        "0.9",
        "2024",
        "0.0000001",
        "123456789012",
    ]
    assert encode_values(2024, "x") == ["2024"]
    assert encode_values("b", "x") == ["b"]
    assert encode_values(dt.date(2026, 1, 2), "x") == ["2026-01-02"]
    assert encode_values(pd.Timestamp("2026-01-02"), "x") == ["2026-01-02"]
    assert encode_values(np.array([1, 2]), "x") == ["1", "2"]
    assert encode_values(pd.Series(["a", None]), "x") == ["a", "__null__"]
    assert encode_values([float("nan"), pd.NA], "x") == ["__null__"]
    assert encode_values(np.bool_(True), "x") == ["true"]
    assert encode_values(("a", "a", "b"), "x") == ["a", "b"]
    with pytest.raises(TypeError, match="Filter `subject` must be strings"):
        encode_values([object()], "subject")
    with pytest.raises(TypeError, match="flat list"):
        encode_values([["a"]], "subject")
    with pytest.raises(TypeError, match="not a dict"):
        encode_values({"a": 1}, "subject")


def test_format_number_never_uses_scientific_notation():
    assert format_number(1e6) == "1000000"
    assert format_number(0.25) == "0.25"
    assert format_number(-3) == "-3"
    assert format_number(1e-20) == "0"
    assert format_number(True) == "true"


def test_encode_years_sends_runs_as_ranges_and_the_rest_as_lists():
    assert encode_years(None) == {}
    assert encode_years(2024) == {"year": ["2024"]}
    assert encode_years(range(2019, 2025)) == {"year_min": ["2019"], "year_max": ["2024"]}
    assert encode_years([2024, 2019, 2020, 2021, 2022, 2023]) == {
        "year_min": ["2019"],
        "year_max": ["2024"],
    }
    assert encode_years([2019, 2024]) == {"year": ["2019", "2024"]}
    assert encode_years([2020, 2020]) == {"year": ["2020"]}
    assert encode_years(np.int64(2024)) == {"year": ["2024"]}
    assert encode_years(2024.0) == {"year": ["2024"]}
    with pytest.raises(TypeError, match="whole year"):
        encode_years("2024")
    with pytest.raises(ValueError, match="whole year"):
        encode_years(2024.5)
    with pytest.raises(ValueError, match="whole year"):
        encode_years([])
    with pytest.raises(TypeError, match="whole year"):
        encode_years(True)


def test_encode_filters_encodes_named_filters_and_renames_school_id():
    out = encode_filters(
        {
            "demographic": ["all", "black", "all"],
            "school_id": "761-0199",
            "active": True,
            "graduation_rate_min": 0.9,
            "assessment_type": [None],
            "skipped": None,
        }
    )
    assert out == {
        "demographic": ["all", "black"],
        "school": ["761-0199"],
        "active": ["true"],
        "graduation_rate_min": ["0.9"],
        "assessment_type": ["__null__"],
    }
    assert encode_filters({}) == {}


def test_encode_filters_refuses_empty_reserved_and_school_filters():
    with pytest.raises(ValueError, match="`subject` is empty"):
        encode_filters({"subject": []})
    with pytest.raises(ValueError, match="`limit` can't be given as a filter"):
        encode_filters({"limit": 5})
    with pytest.raises(ValueError, match="Use `school_id`"):
        encode_filters({"school": "761-0199"})


def test_dataset_query_merges_years_filters_places_and_options():
    places = Places(district_code=["660"], school_pairs=["660-0191"])
    q = dataset_query(
        {"demographic": ["all"]},
        {"year": ["2024"]},
        "schools",
        places,
        columns=["year", "school_code"],
        sort=["-year"],
    )
    assert q == {
        "year": ["2024"],
        "detail": ["schools"],
        "demographic": ["all"],
        "district_code": ["660"],
        "school": ["660-0191"],
        "columns": ["year", "school_code"],
        "sort": ["-year"],
    }
    assert dataset_query({}, {}, None, Places()) == {}
    merged = dataset_query(
        {"county_fips": ["13121"], "district_code": ["761"]},
        {},
        None,
        Places(district_code=["660", "761"], county_fips=["13089"]),
    )
    assert merged["district_code"] == ["761", "660"]
    assert merged["county_fips"] == ["13121", "13089"]


def test_dataset_request_switches_to_post_for_very_long_urls():
    short = dataset_request("employment", "rows", {"county_fips": ["13121"]})
    assert short.method == "GET"
    assert short.url.endswith("datasets/employment/rows?county_fips=13121")

    tracts = [f"13121{i:06d}" for i in range(1, 601)]
    long = dataset_request("employment", "rows", {"tract_geoid": tracts, "detail": ["tracts"]})
    assert long.method == "POST"
    assert long.url.endswith("datasets/employment/query")
    assert len(long.json_body["tract_geoid"]) == 600
    assert long.json_body["detail"] == ["tracts"]

    values = dataset_request("employment", "values", {"tract_geoid": tracts})
    assert values.method == "GET"


def test_check_query_args_wants_one_detail_level():
    with pytest.raises(ValueError, match="one detail level"):
        check_query_args(["states", "districts"], None, None)
    with pytest.raises(TypeError, match="`columns` must be"):
        check_query_args(None, ["year", None], None)
    with pytest.raises(TypeError, match="`sort` must be"):
        check_query_args(None, None, [])
    assert check_query_args("states", "year", ["-year"]) == (["year"], ["-year"])


def test_check_n_max():
    assert check_n_max(None) == math.inf
    assert check_n_max(5) == 5
    for bad in (0, -1, "5", True, float("nan")):
        with pytest.raises(ValueError, match="`n_max`"):
            check_n_max(bad)
