from __future__ import annotations

import pandas as pd
import pytest

import georgiacivicdata as gcd
from helpers import (
    error_response,
    json_response,
    recorded,
    seed_grad_schema,
    seed_meta,
    seed_recorded,
    url,
)

GRAD = "graduation_rate_4_year_cohort"


def test_values_lists_combinations_with_row_counts(api, tables):
    api.get(url("datasets", GRAD)).mock(return_value=recorded(f"m/vals/g/d/{GRAD}.json"))
    route = api.get(url("datasets", GRAD, "values")).mock(
        return_value=recorded(f"m/vals/g/d/{GRAD}/values-42f841.json")
    )
    out = gcd.values(GRAD, "demographic", district="Fulton County", year=2024, detail="districts")
    params = route.calls.last.request.url.params
    assert params["district_code"] == "660"
    assert params["columns"] == "demographic"
    assert list(out.columns) == ["demographic", "n_rows"]
    assert str(out["n_rows"].dtype) == "Int64"
    assert "all" in out["demographic"].tolist()
    counts = out["n_rows"].tolist()
    assert counts == sorted(counts, reverse=True)


def test_values_warns_at_the_500_combination_cap_and_types_values(api):
    seed_grad_schema()
    api.get(url("datasets", GRAD, "values")).mock(
        return_value=json_response(
            {
                "dataset": GRAD,
                "columns": ["year", "demographic"],
                "total_combinations": 900,
                "truncated": True,
                "data": [
                    {"year": 2024, "demographic": "all", "count": 10},
                    {"year": 2023, "demographic": None, "count": 2},
                ],
            }
        )
    )
    with pytest.warns(
        UserWarning,
        match=r"Only the 2 most common combinations are shown \(the API returns at most 500 of 900\)",
    ):
        out = gcd.values(GRAD, ["year", "demographic"])
    assert out["year"].tolist() == [2024, 2023]
    assert out["demographic"].iloc[0] == "all"
    assert pd.isna(out["demographic"].iloc[1])
    assert out["n_rows"].tolist() == [10, 2]


def test_values_as_polars(api):
    pl = pytest.importorskip("polars")
    seed_grad_schema()
    api.get(url("datasets", GRAD, "values")).mock(
        return_value=json_response(
            {"columns": ["subject"], "data": [{"subject": "math", "count": 3}]}
        )
    )
    out = gcd.values(GRAD, "subject", backend="polars")
    assert isinstance(out, pl.DataFrame)
    assert out.columns == ["subject", "n_rows"]


def test_values_needs_columns():
    with pytest.raises(TypeError, match="`columns` must be"):
        gcd.values("x", None)
    with pytest.raises(TypeError, match="`columns` must be"):
        gcd.values("x", [])


# Lookup tables ---------------------------------------------------------------


def test_dimension_returns_a_whole_lookup_table_cached(api):
    api.get(url("dimensions", "counties")).mock(return_value=recorded("m/dim/g/m/counties.json"))
    route = api.get(url("dimensions", "counties", "rows")).mock(
        return_value=recorded("m/dim/g/m/counties/rows-701f1d.json")
    )
    counties = gcd.dimension("counties")
    again = gcd.dimension("counties")
    three = gcd.dimension("counties", n_max=3)
    assert route.call_count == 1
    assert len(counties) == 159
    assert list(counties.columns) == ["county_fips", "county_name"]
    pd.testing.assert_frame_equal(counties, again)
    assert len(three) == 3
    assert counties.set_index("county_fips").loc["13121", "county_name"] == "Fulton"


def test_dimension_filters_on_the_server_and_types_from_the_schema(api):
    api.get(url("dimensions", "schools")).mock(return_value=recorded("m/dim2/g/m/schools.json"))
    api.get(url("dimensions", "schools", "rows"), params__contains={"q": "eastside"}).mock(
        return_value=recorded("m/dim2/g/m/schools/rows-3ddc90.json")
    )
    route = api.get(
        url("dimensions", "schools", "rows"), params__contains={"district_code": "630"}
    ).mock(return_value=recorded("m/dim2/g/m/schools/rows-d319a6.json"))
    clay = gcd.dimension("schools", district_code="630", active=True)
    found = gcd.dimension(
        "schools", q="eastside", columns=["district_code", "school_code", "school_name"], n_max=2
    )
    assert route.calls.last.request.url.params["active"] == "true"
    assert (clay["district_code"] == "630").all()
    assert clay["active"].all()
    assert clay["latitude"].dtype == "float64"
    assert str(clay["directory_year"].dtype) == "Int64"
    assert str(clay["charter"].dtype) == "boolean"
    assert list(found.columns) == ["district_code", "school_code", "school_name"]
    assert len(found) == 2
    assert found["school_name"].str.contains("eastside", case=False).all()


def test_school_names_become_code_filters_and_exact_pairs(api, tables):
    seed_recorded("m/descl/g/m/schools.json", ["dimensions", "schools"])
    route = api.get(url("dimensions", "schools", "rows")).mock(
        return_value=json_response(
            {
                "data": [
                    {
                        "district_code": "634",
                        "school_code": "0282",
                        "school_name": "Eastside Elementary School",
                    },
                    {"district_code": "634", "school_code": "2052", "school_name": "Other"},
                    {
                        "district_code": "638",
                        "school_code": "2052",
                        "school_name": "Eastside Elementary School",
                    },
                ],
                "pagination": {"has_more": False},
            }
        )
    )
    out = gcd.dimension(
        "schools",
        school="Eastside Elementary School",
        district=["Coffee County", "Coweta County"],
        columns="school_name",
    )
    params = route.calls.last.request.url.params
    assert params["district_code"] == "634,638"
    assert params["school_code"] == "0282,2052"
    assert params["columns"] == "school_name,district_code,school_code"
    assert out["school_name"].tolist() == ["Eastside Elementary School"] * 2
    assert list(out.columns) == ["school_name"]
    capped = gcd.dimension(
        "schools",
        school="Eastside Elementary School",
        district=["Coffee County", "Coweta County"],
        n_max=1,
    )
    assert len(capped) == 1


def test_dimension_pages_past_10000_rows(api):
    seed_meta(
        ["dimensions", "block_groups"],
        {
            "name": "block_groups",
            "columns": [
                {"name": "block_group_geoid", "type": "string"},
                {"name": "population_2020", "type": "integer"},
            ],
        },
    )
    urls = []

    def respond(request):
        urls.append(str(request.url))
        second = "offset" in request.url.params
        return json_response(
            {
                "data": [{"block_group_geoid": "2" if second else "1", "population_2020": 5}],
                "pagination": {"has_more": not second},
            }
        )

    api.get(url("dimensions", "block_groups", "rows")).mock(side_effect=respond)
    out = gcd.dimension("block_groups", county_fips="13121")
    assert out["block_group_geoid"].tolist() == ["1", "2"]
    assert out["population_2020"].tolist() == [5, 5]
    assert "offset=1" in urls[1]


def test_dimension_with_no_rows_keeps_typed_columns(api):
    seed_meta(
        ["dimensions", "counties"],
        {
            "name": "counties",
            "columns": [
                {"name": "county_fips", "type": "string"},
                {"name": "n", "type": "integer"},
            ],
        },
    )
    api.get(url("dimensions", "counties", "rows")).mock(
        return_value=json_response({"data": [], "pagination": {"has_more": False}})
    )
    out = gcd.dimension("counties", q="zzz", backend="pandas")
    assert list(out.columns) == ["county_fips", "n"]
    assert str(out["n"].dtype) == "Int64"


def test_dimension_checks_names_and_arguments(api, tables):
    seed_meta(
        ["dimensions", "counties"],
        {
            "name": "counties",
            "columns": [
                {"name": "county_fips", "type": "string"},
                {"name": "county_name", "type": "string"},
            ],
        },
    )
    with pytest.raises(gcd.GCDError, match='`school` doesn\'t apply: the lookup table "counties"'):
        gcd.dimension("counties", school="Roswell High School")
    with pytest.raises(TypeError, match="`q` must be a single string"):
        gcd.dimension("counties", q=["a", "b"])
    with pytest.raises(ValueError, match="`n_max`"):
        gcd.dimension("counties", n_max=-1)
    api.get(url("dimensions", "countys")).mock(
        return_value=error_response(
            404,
            "DIM_NOT_FOUND",
            "No lookup table 'countys'",
            {"available": ["districts", "schools", "counties"], "did_you_mean": ["counties"]},
        )
    )
    with pytest.raises(gcd.GCDNotFoundError) as info:
        gcd.dimension("countys")
    assert str(info.value) == (
        "No lookup table 'countys'\n"
        "  Did you mean: 'counties'?\n"
        "  Available: 'districts', 'schools', 'counties'."
    )
