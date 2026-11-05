from __future__ import annotations

import warnings

import pandas as pd
import pytest

import georgiacivicdata as gcd
from helpers import json_response, recorded, url

COMPACT = [
    "name",
    "title",
    "summary",
    "kind",
    "main_topic",
    "detail_levels",
    "year_min",
    "year_max",
]
SEARCH = [
    "rank",
    "name",
    "title",
    "summary",
    "main_topic",
    "detail_levels",
    "year_min",
    "year_max",
    "score",
    "matched_on",
    "matched_columns",
]


def test_datasets_returns_the_compact_catalog_typed(api):
    route = api.get(url("datasets"), params={"main_topic": "immigration"}).mock(
        return_value=recorded("m/cat/g/datasets-9093d3.json")
    )
    out = gcd.datasets(main_topic="immigration")
    assert route.called
    assert isinstance(out, pd.DataFrame)
    assert list(out.columns) == COMPACT
    assert len(out) > 0
    assert (out["main_topic"] == "immigration").all()
    assert isinstance(out["detail_levels"].iloc[0], list)
    assert str(out["year_min"].dtype) == "Int64"
    assert not {"sub_topic", "topic", "key"} & set(out.columns)


def test_details_adds_the_long_columns(api):
    api.get(url("datasets"), params={"main_topic": "immigration", "fields": "full"}).mock(
        return_value=recorded("m/catf/g/datasets-0aa40e.json")
    )
    api.get(url("datasets"), params={"kind": "geometry", "fields": "full"}).mock(
        return_value=recorded("m/catf/g/datasets-b3e9d1.json")
    )
    out = gcd.datasets(main_topic="immigration", details=True)
    geo = gcd.datasets(kind="geometry", details=True)
    assert list(out.columns) == [
        *COMPACT,
        "description",
        "source",
        "source_url",
        "grain",
        "default_detail",
        "year_gaps",
        "update_frequency",
        "search_aliases_en",
        "search_aliases_es",
        "updated_at",
    ]
    assert str(out["updated_at"].dtype).startswith("datetime64")
    assert "UTC" in str(out["updated_at"].dtype)
    assert all(isinstance(g, str) for g in out["grain"].iloc[0])
    assert all(isinstance(y, int) for row in out["year_gaps"] for y in row)
    assert isinstance(out["search_aliases_es"].iloc[0], list)
    assert sorted(geo["name"]) == ["school_attendance_zones", "school_district_boundaries"]
    assert (geo["kind"] == "geometry").all()
    assert geo["updated_at"].isna().all()


def test_datasets_as_polars(api):
    pl = pytest.importorskip("polars")
    api.get(url("datasets"), params={"main_topic": "immigration"}).mock(
        return_value=recorded("m/cat/g/datasets-9093d3.json")
    )
    out = gcd.datasets(main_topic="immigration", backend="polars")
    assert isinstance(out, pl.DataFrame)
    assert out.columns == COMPACT
    assert out.schema["detail_levels"] == pl.List(pl.String)


def test_datasets_checks_its_arguments():
    with pytest.raises(ValueError, match="`kind` must be 'table' or 'geometry'"):
        gcd.datasets(kind="tables")
    with pytest.raises(TypeError, match="`main_topic` must be a single string"):
        gcd.datasets(main_topic=["census", "health"])
    with pytest.raises(TypeError, match="`level` must be a single string"):
        gcd.datasets(level=1)
    with pytest.raises(TypeError, match="`year` must be a single year"):
        gcd.datasets(year=[2019, 2020])
    with pytest.raises(TypeError, match="`details` must be True or False"):
        gcd.datasets(details=None)
    with pytest.raises(ValueError, match="`backend`"):
        gcd.datasets(backend="arrow")


def test_search_ranks_datasets(api):
    route = api.get(url("search")).mock(return_value=recorded("m/srch/g/search-6e7254.json"))
    out = gcd.search("graduation rate", n=3, level="schools", main_topic="education", year=2024)
    params = route.calls.last.request.url.params
    assert params["limit"] == "3"
    assert params["year"] == "2024"
    assert list(out.columns) == SEARCH
    assert out["rank"].tolist() == [1, 2, 3]
    assert out["score"].dtype == "float64"
    assert isinstance(out["matched_on"].iloc[0], list)
    assert "graduation_rate_4_year_cohort" in out["name"].tolist()
    info = gcd.meta(out)
    assert info["confidence"] in ("high", "medium", "low")
    assert set(info["retrieval"]) == {"mode", "reranked"}
    assert not {"sub_topic", "topic", "key"} & set(out.columns)


def test_search_reports_low_confidence_keyword_fallback_and_lookup_tables(api):
    api.get(url("search")).mock(
        return_value=json_response(
            {
                "query": "school addresses",
                "matches": [],
                "match_count": 0,
                "total_matches": 0,
                "truncated": False,
                "confidence": "low",
                "retrieval": {"mode": "keyword", "reranked": False},
                "dimension_matches": [
                    {"name": "schools", "matched_on": ["aliases"]},
                    {"name": "counties", "matched_on": []},
                ],
            }
        )
    )
    with pytest.warns(gcd.GCDAdvisory) as record:
        out = gcd.search("school addresses")
    assert [str(w.message) for w in record] == [
        "Nothing in the catalog may fit this query.",
        "Search fell back to keywords only, so matches by meaning are missing.",
        "Lookup tables that match: 'schools'. See gcd.dimension().",
    ]
    assert len(out) == 0
    assert list(out.columns) == SEARCH
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        gcd.search("school addresses", quiet=True)
        with gcd.option_context(quiet=True):
            gcd.search("school addresses")


def test_search_checks_its_arguments():
    with pytest.raises(TypeError, match="non-empty string"):
        gcd.search("")
    with pytest.raises(TypeError, match="non-empty string"):
        gcd.search(["a", "b"])
    with pytest.raises(ValueError, match="from 1 to 100"):
        gcd.search("jobs", n=0)
    with pytest.raises(ValueError, match="from 1 to 100"):
        gcd.search("jobs", n=101)
    with pytest.raises(TypeError, match="single year"):
        gcd.search("jobs", year="2024")
