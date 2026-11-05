"""End-to-end calls against the production API.

They run only when GCD_LIVE_TESTS=true (the weekly GitHub Actions workflow),
never offline and never in the regular CI, to keep traffic off the
platform's usage metric.
"""

from __future__ import annotations

import pytest

import georgiacivicdata as gcd
from georgiacivicdata import _cache
from helpers import LIVE

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not LIVE, reason="GCD_LIVE_TESTS is not true"),
]


def test_live_the_catalog_search_and_a_schema():
    catalog = gcd.datasets()
    assert len(catalog) > 100
    assert set(catalog["kind"]) == {"table", "geometry"}
    assert len(gcd.search("graduation", n=5, quiet=True)) > 0
    d = gcd.describe("graduation_rate_4_year_cohort")
    assert d.key_metric == "graduation_rate"
    assert {"districts", "schools", "states"} <= set(d.detail_levels)


def test_live_rows_by_name_typed_with_metadata():
    out = gcd.rows(
        "graduation_rate_4_year_cohort",
        district="Fulton County",
        school="Roswell High School",
        demographic="all",
        year=2024,
        quiet=True,
    )
    assert len(out) == 1
    assert out["school_code"].tolist() == ["0191"]
    assert out["graduation_rate"].dtype == "float64"
    assert "Georgia Civic Data" in gcd.citation(out)


def test_live_polars_rows():
    pl = pytest.importorskip("polars")
    out = gcd.rows("employment", county_fips="13121", year=2024, quiet=True, backend="polars")
    assert isinstance(out, pl.DataFrame)
    assert out["county_fips"].to_list() == ["13121"] * len(out)


def test_live_a_result_over_10000_rows_downloads_as_csv():
    out = gcd.rows(
        "graduation_rate_4_year_cohort",
        year=[2023, 2024],
        detail="schools",
        labels=False,
        quiet=True,
    )
    assert len(out) > 10000
    assert str(out["year"].dtype) == "Int64"
    assert (out["school_code"].str.len() == 4).all()


def test_live_the_disk_cache_revalidates_with_the_etag():
    first = gcd.rows("employment", county_fips="13121", year=2024, cache=True, quiet=True)
    files = list(_cache.cache_dir().glob("*.body"))
    assert files
    second = gcd.rows("employment", county_fips="13121", year=2024, cache=True, quiet=True)
    assert first.equals(second)


def test_live_zones_coverage_and_a_located_landmark():
    pytest.importorskip("geopandas")
    zones = gcd.school_zones(district_code="630")
    assert zones.crs.to_epsg() == 4326
    assert len(gcd.school_zone_coverage()) > 100
    here = gcd.locate(lat=33.749, lon=-84.388, quiet=True)
    assert here["geographic_type"].tolist()[:4] == [
        "county",
        "tract",
        "block_group",
        "school_district",
    ]
    assert here["geographic_name"].iloc[0] == "Fulton"


def test_live_the_state_capitols_address_geocodes_through_the_census():
    out = gcd.locate(address="206 Washington St SW, Atlanta, GA 30334", quiet=True)
    assert set(out["match_status"]) == {"match"}
    assert out.loc[out["geographic_type"] == "county", "geographic_id"].tolist() == ["13121"]
