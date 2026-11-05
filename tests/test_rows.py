from __future__ import annotations

import json
import warnings

import httpx
import pandas as pd
import pytest

import georgiacivicdata as gcd
from georgiacivicdata import _cache
from helpers import json_response, recorded, seed_grad_schema, url

GRAD = "graduation_rate_4_year_cohort"


def test_rows_returns_typed_rows_with_names_beside_codes(api, tables):
    api.get(url("datasets", GRAD)).mock(return_value=recorded(f"m/rows/g/d/{GRAD}.json"))
    route = api.get(url("datasets", GRAD, "rows")).mock(
        return_value=recorded(f"m/rows/g/d/{GRAD}/rows-7be007.json")
    )
    with pytest.warns(gcd.GCDAdvisory) as record:
        out = gcd.rows(
            GRAD,
            district="Fulton County",
            school="Roswell High School",
            year=2024,
            demographic=["all", "black"],
        )
    assert len(record) >= 1
    params = route.calls.last.request.url.params
    assert params["school"] == "660-0191"
    assert params["demographic"] == "all,black"
    assert params["limit"] == "10000"
    assert isinstance(out, pd.DataFrame)
    assert list(out.columns) == [
        "year",
        "district_code",
        "district_name",
        "district_census_id",
        "district_type",
        "school_code",
        "school_name",
        "demographic",
        "demographic_label",
        "demographic_category",
        "num_graduates",
        "num_cohort",
        "graduation_rate",
    ]
    assert str(out["year"].dtype) == "Int64"
    assert str(out["num_graduates"].dtype) == "Int64"
    assert out["graduation_rate"].dtype == "float64"
    assert str(out["school_code"].dtype) == "string"
    assert (out["graduation_rate"].dropna() <= 1).all()
    assert out["school_code"].unique().tolist() == ["0191"]
    assert out["district_census_id"].unique().tolist() == ["02280"]
    assert set(out["demographic"]) == {"all", "black"}

    info = gcd.meta(out)
    assert info["dataset"] == GRAD
    assert "key" not in info
    assert isinstance(info["advisories"], list)
    assert "school=660-0191" in info["request_url"]
    assert gcd.citation(out).startswith("Four-Year Cohort Graduation Rate. Georgia Civic Data")
    assert [str(w.message) for w in record] == [a["message"] for a in info["advisories"]]


def mock_rows2(api):
    api.get(url("datasets", GRAD)).mock(return_value=recorded(f"m/rows2/g/d/{GRAD}.json"))
    api.get(url("datasets", GRAD, "rows"), params__contains={"detail": "states"}).mock(
        return_value=recorded(f"m/rows2/g/d/{GRAD}/rows-4a6f07.json")
    )
    api.get(
        url("datasets", GRAD, "rows"),
        params__contains={
            "columns": "year,district_code,school_code,demographic,num_graduates,num_cohort,graduation_rate"
        },
    ).mock(return_value=recorded(f"m/rows2/g/d/{GRAD}/rows-8bf779.json"))
    api.get(url("datasets", GRAD, "rows")).mock(
        return_value=recorded(f"m/rows2/g/d/{GRAD}/rows-c01e87.json")
    )


def test_labels_false_gives_the_same_shape_without_the_names(api):
    mock_rows2(api)
    common = {"district_code": "660", "detail": "districts", "year": 2024, "demographic": "all"}
    with_labels = gcd.rows(GRAD, **common, quiet=True)
    without = gcd.rows(GRAD, **common, labels=False, quiet=True)
    states = gcd.rows(
        GRAD, detail="states", year=2024, sort="-graduation_rate", n_max=3, quiet=True
    )
    assert "school_code" not in with_labels.columns
    assert list(without.columns) == [
        c
        for c in with_labels.columns
        if c
        not in (
            "district_name",
            "district_census_id",
            "district_type",
            "demographic_label",
            "demographic_category",
        )
    ]
    assert without["num_graduates"].tolist() == with_labels["num_graduates"].tolist()
    assert len(states) == 3
    assert "district_code" not in states.columns
    rates = states["graduation_rate"].dropna().tolist()
    assert rates == sorted(rates, reverse=True)


def test_rows_as_polars(api):
    pl = pytest.importorskip("polars")
    mock_rows2(api)
    out = gcd.rows(
        GRAD,
        district_code="660",
        detail="districts",
        year=2024,
        demographic="all",
        quiet=True,
        backend="polars",
    )
    assert isinstance(out, pl.DataFrame)
    assert out.schema["year"] == pl.Int64
    assert out.schema["district_code"] == pl.String
    assert gcd.meta(out)["dataset"] == GRAD
    gcd.set_option("backend", "polars")
    assert isinstance(
        gcd.rows(
            GRAD, district_code="660", detail="districts", year=2024, demographic="all", quiet=True
        ),
        pl.DataFrame,
    )


CSV = "\n".join(
    [
        "year,district_code,school_code,demographic,num_graduates,num_cohort,graduation_rate,"
        "district_name,district_census_id,district_type,school_name,demographic_label,"
        "demographic_category",
        "2024,660,0103,all,100,110,0.9090909090909091,Fulton County,02280,standard,A School,All,aggregate",
        "2024,660,0104,all,,,,Fulton County,02280,standard,B School,All,aggregate",
        '2024,660,0105,all,3000000000,3000000001,0.99,Fulton County,02280,standard,"C, School",All,aggregate',
    ]
)


def test_results_larger_than_one_page_download_as_csv(api, capsys):
    seed_grad_schema()
    seen = []

    def respond(request):
        seen.append(str(request.url))
        if request.url.params.get("format") == "csv":
            return httpx.Response(200, content=CSV.encode(), headers={"content-type": "text/csv"})
        return json_response(
            {
                "data": [
                    {
                        "year": 2024,
                        "district_code": "660",
                        "school_code": "0103",
                        "demographic": "all",
                    }
                ],
                "pagination": {
                    "limit": 1,
                    "offset": 0,
                    "total": 3,
                    "returned": 1,
                    "has_more": True,
                },
                "meta": {
                    "dataset": GRAD,
                    "key": "a/b/c",
                    "title": "Four-Year Cohort Graduation Rate",
                    "advisories": [{"code": "x", "message": "An advisory."}],
                },
            }
        )

    api.get(url("datasets", GRAD, "rows")).mock(side_effect=respond)
    with pytest.warns(gcd.GCDAdvisory, match="An advisory."):
        out = gcd.rows(GRAD, district_code="660")
    assert "i Downloading 3 rows as CSV." in capsys.readouterr().err
    assert len(out) == 3
    assert out["school_code"].tolist() == ["0103", "0104", "0105"]
    assert out["num_graduates"].iloc[0] == 100
    assert pd.isna(out["num_graduates"].iloc[1])
    assert out["num_graduates"].iloc[2] == 3000000000
    assert str(out["year"].dtype) == "Int64"
    assert out["school_name"].iloc[2] == "C, School"
    assert list(out.columns[:5]) == [
        "year",
        "district_code",
        "district_name",
        "district_census_id",
        "district_type",
    ]
    assert "limit=10000" in seen[0]
    assert "limit" not in seen[1]
    assert [a["code"] for a in gcd.meta(out)["advisories"]] == ["x"]

    # a cap above one page keeps the first n_max rows of the CSV
    capped = gcd.rows(GRAD, district_code="660", n_max=10002, quiet=True)
    assert len(capped) == 3
    with pytest.warns(gcd.GCDAdvisory):
        gcd.rows(GRAD, district_code="660", n_max=10002)
    assert "keeping the first 3" not in capsys.readouterr().err
    # n_max within one page asks for that many rows and never downloads CSV
    seen.clear()
    gcd.rows(GRAD, district_code="660", n_max=1, quiet=True)
    assert len(seen) == 1
    assert seen[0].endswith("limit=1")


def test_the_csv_note_says_when_rows_are_capped(api, capsys):
    seed_grad_schema()

    def respond(request):
        if request.url.params.get("format") == "csv":
            return httpx.Response(200, content=CSV.encode())
        return json_response(
            {"data": [{"year": 2024}], "pagination": {"total": 20000, "has_more": True}, "meta": {}}
        )

    api.get(url("datasets", GRAD, "rows")).mock(side_effect=respond)
    out = gcd.rows(GRAD, n_max=15000)
    assert "Downloading 20,000 rows as CSV (keeping the first 15,000)." in capsys.readouterr().err
    assert len(out) == 3


def test_long_filter_lists_go_as_post_query_and_empty_results_keep_columns(api):
    seed_grad_schema()
    route = api.post(url("datasets", GRAD, "query")).mock(
        return_value=json_response(
            {
                "data": [],
                "pagination": {
                    "limit": 10000,
                    "offset": 0,
                    "total": 0,
                    "returned": 0,
                    "has_more": False,
                },
                "meta": {
                    "dataset": GRAD,
                    "omitted_columns": ["school_code", "school_name"],
                    "advisories": [],
                },
            }
        )
    )
    codes = [f"{i:07d}" for i in range(1, 801)]
    out = gcd.rows(GRAD, district_code=codes, detail="districts", year=[2019, 2024])
    body = json.loads(route.calls.last.request.content)
    assert len(body["district_code"]) == 800
    assert body["year"] == ["2019", "2024"]
    assert body["limit"] == ["10000"]
    assert len(out) == 0
    assert "school_code" not in out.columns
    assert {"district_name", "graduation_rate"} <= set(out.columns)
    assert out["graduation_rate"].dtype == "float64"
    assert gcd.meta(out)["advisories"] == []


def test_cache_true_sends_the_rows_request_through_the_disk_cache(api):
    seed_grad_schema()
    route = api.get(url("datasets", GRAD, "rows")).mock(
        side_effect=[
            json_response(
                {"data": [], "pagination": {"has_more": False}, "meta": {}},
                headers={"etag": '"v1"'},
            ),
            httpx.Response(304),
            json_response({"data": [], "pagination": {"has_more": False}, "meta": {}}),
        ]
    )
    gcd.rows(GRAD, year=2024, cache=True)
    assert any(_cache.cache_dir().iterdir())
    gcd.set_option("cache", True)
    gcd.rows(GRAD, year=2024)
    assert route.calls[1].request.headers["if-none-match"] == '"v1"'
    gcd.rows(GRAD, year=2024, cache=False)
    assert "if-none-match" not in route.calls[2].request.headers


def test_advisories_are_silenced_by_quiet_and_the_option(api):
    seed_grad_schema()
    api.get(url("datasets", GRAD, "rows")).mock(
        return_value=json_response(
            {
                "data": [{"year": 2024}],
                "pagination": {"has_more": False},
                "meta": {"advisories": [{"code": "a", "message": "Watch out."}]},
            }
        )
    )
    with pytest.warns(gcd.GCDAdvisory, match="Watch out"):
        gcd.rows(GRAD)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        gcd.rows(GRAD, quiet=True)
        gcd.set_option("quiet", True)
        out = gcd.rows(GRAD)
    assert gcd.meta(out)["advisories"] == [{"code": "a", "message": "Watch out."}]


def test_advisories_point_at_the_callers_line(api):
    seed_grad_schema()
    api.get(url("datasets", GRAD, "rows")).mock(
        return_value=json_response(
            {
                "data": [],
                "pagination": {},
                "meta": {"advisories": [{"code": "a", "message": "Hi."}]},
            }
        )
    )
    with pytest.warns(gcd.GCDAdvisory) as record:
        gcd.rows(GRAD)
    assert record[0].filename == __file__


def test_rows_checks_its_arguments_before_any_request():
    with pytest.raises(TypeError, match="single string"):
        gcd.rows(1)
    with pytest.raises(ValueError, match="`limit` can't be given as a filter"):
        gcd.rows("x", limit=10)
    with pytest.raises(ValueError, match="one detail level"):
        gcd.rows("x", detail=["states", "districts"])
    with pytest.raises(ValueError, match="`n_max`"):
        gcd.rows("x", n_max=0)
    with pytest.raises(TypeError, match="`labels` must be True or False"):
        gcd.rows("x", labels="no")
    with pytest.raises(TypeError, match="`cache` must be True or False"):
        gcd.rows("x", cache="no")
    with pytest.raises(gcd.GCDError, match="'counties' is a lookup table"):
        gcd.rows("counties")
