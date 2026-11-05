from __future__ import annotations

import builtins

import pandas as pd
import pytest

import georgiacivicdata as gcd
from georgiacivicdata._zones import check_year1, normalize_grade, served_for_level
from helpers import json_response, recorded, seed_recorded, url

ZONE_COLUMNS = [
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
]
STATUS_COLUMNS = [
    "year",
    "district_code",
    "district_name",
    "school_code",
    "school_name",
    "zone_status",
    "zone_levels",
    "no_zone_category",
    "reason",
]


def seed_zone_schema():
    seed_recorded(
        "m/descg/g/d/school_attendance_zones.json", ["datasets", "school_attendance_zones"]
    )


def test_normalize_grade_accepts_the_usual_spellings():
    assert normalize_grade("5") == "05"
    assert normalize_grade(9) == "09"
    assert normalize_grade("K") == "k"
    assert normalize_grade("Kindergarten") == "k"
    assert normalize_grade("Pre-K") == "pk"
    assert normalize_grade("12") == "12"
    assert normalize_grade(None) is None
    with pytest.raises(ValueError, match="`grade` must be one of"):
        normalize_grade("13")
    with pytest.raises(TypeError, match="`grade` must be one grade"):
        normalize_grade(["1", "2"])
    with pytest.raises(TypeError, match="`year` must be a single year"):
        check_year1("2027")
    assert check_year1(2027) == "2027"


def test_school_zones_returns_zone_attributes_without_geometry(api):
    seed_zone_schema()
    route = api.get(url("datasets", "school_attendance_zones", "rows")).mock(
        return_value=recorded("m/zone/g/d/school_attendance_zones/rows-b7d4bf.json")
    )
    out = gcd.school_zones(district_code="630", geometry=False)
    params = route.calls.last.request.url.params
    assert params["format"] == "json"
    assert params["resolution"] == "display"
    assert isinstance(out, pd.DataFrame)
    assert "geometry" not in out.columns
    assert list(out.columns[: len(ZONE_COLUMNS)]) == ZONE_COLUMNS
    assert str(out["year"].dtype) == "Int64"
    assert str(out["retrieved_on"].dtype).startswith("datetime64")
    assert out["district_name"].unique().tolist() == ["Clay County"]
    assert "Not an official enrollment determination" in gcd.meta(out)["note"]


def test_school_zones_as_polars(api):
    pl = pytest.importorskip("polars")
    seed_zone_schema()
    api.get(url("datasets", "school_attendance_zones", "rows")).mock(
        return_value=recorded("m/zone/g/d/school_attendance_zones/rows-b7d4bf.json")
    )
    out = gcd.school_zones(district_code="630", geometry=False, backend="polars")
    assert isinstance(out, pl.DataFrame)
    assert out.schema["retrieved_on"] == pl.Date
    with pytest.raises(ValueError, match="Use geometry=False for a Polars"):
        gcd.school_zones(district_code="630", backend="polars")


def test_school_zones_returns_a_geodataframe(api):
    gpd = pytest.importorskip("geopandas")
    seed_zone_schema()
    api.get(url("datasets", "school_attendance_zones", "rows")).mock(
        return_value=recorded("m/zoneg/g/d/school_attendance_zones/rows-f52004.txt")
    )
    out = gcd.school_zones(district_code="630", zone_level="middle")
    assert isinstance(out, gpd.GeoDataFrame)
    assert list(out.columns[: len(ZONE_COLUMNS)]) == ZONE_COLUMNS
    assert out.crs.to_epsg() == 4326
    assert (out["zone_level"] == "middle").all()
    assert out.geometry.is_valid.all()
    assert str(out["retrieved_on"].dtype).startswith("datetime64")
    assert "Not an official" in gcd.meta(out)["note"]


def test_school_names_become_code_filters_and_exact_pairs_for_zones(api, tables):
    seed_zone_schema()
    route = api.get(url("datasets", "school_attendance_zones", "rows")).mock(
        return_value=json_response(
            {
                "data": [
                    {
                        "year": 2027,
                        "district_code": "634",
                        "school_code": "0282",
                        "zone_level": "elementary",
                    },
                    {
                        "year": 2027,
                        "district_code": "634",
                        "school_code": "2052",
                        "zone_level": "elementary",
                    },
                    {
                        "year": 2027,
                        "district_code": "638",
                        "school_code": "2052",
                        "zone_level": "elementary",
                    },
                ],
                "count": 3,
                "note": "A note.",
            }
        )
    )
    out = gcd.school_zones(
        school="Eastside Elementary School",
        district=["Coffee County", "Coweta County"],
        grade="K",
        year=2027,
        resolution="full",
        geometry=False,
    )
    params = route.calls.last.request.url.params
    assert params["district_code"] == "634,638"
    assert params["school_code"] == "0282,2052"
    assert params["grade"] == "k"
    assert params["year"] == "2027"
    assert params["resolution"] == "full"
    assert (out["district_code"] + " " + out["school_code"]).tolist() == ["634 0282", "638 2052"]
    assert gcd.meta(out)["note"] == "A note."


def test_empty_zones_keep_their_columns(api):
    seed_zone_schema()
    api.get(url("datasets", "school_attendance_zones", "rows")).mock(
        return_value=json_response({"data": [], "count": 0})
    )
    out = gcd.school_zones(district_code="000", geometry=False)
    assert len(out) == 0
    assert list(out.columns[: len(ZONE_COLUMNS)]) == ZONE_COLUMNS


def test_geometry_without_geopandas_points_to_geometry_false(monkeypatch):
    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name == "geopandas":
            raise ImportError("no geopandas")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(ImportError, match=r"georgiacivicdata\[geo\].*geometry=False"):
        gcd.school_zones(geometry=True)
    with pytest.raises(TypeError, match="`geometry` must be True or False"):
        gcd.school_zones(geometry="yes")
    with pytest.raises(ValueError, match="`resolution`"):
        gcd.school_zones(resolution="high")


def test_district_boundaries_fill_department_of_defense_names(api):
    api.get(url("datasets", "school_district_boundaries", "rows")).mock(
        return_value=json_response(
            {
                "data": [
                    {
                        "district_code": None,
                        "district_census_id": "00002",
                        "nces_lea_id": "1300002",
                        "boundary_type": "dodea",
                        "tiger_name": "Fort Benning Schools",
                        "district_name": None,
                    },
                    {
                        "district_code": "630",
                        "district_census_id": "01200",
                        "nces_lea_id": "1301200",
                        "boundary_type": "unified",
                        "tiger_name": "Clay County School District",
                        "district_name": "Clay County",
                    },
                ],
                "count": 2,
            }
        )
    )
    out = gcd.district_boundaries(geometry=False)
    assert list(out.columns[:5]) == [
        "district_code",
        "district_name",
        "boundary_type",
        "district_census_id",
        "nces_lea_id",
    ]
    assert out["district_name"].tolist() == ["Fort Benning Schools", "Clay County"]
    assert pd.isna(out["district_code"].iloc[0])


def test_district_boundaries_read_one_district_as_a_geodataframe(api, tables):
    gpd = pytest.importorskip("geopandas")
    route = api.get(url("datasets", "school_district_boundaries", "rows")).mock(
        return_value=recorded("m/bnd/g/d/school_district_boundaries/rows-8abd74.txt")
    )
    out = gcd.district_boundaries(district="Clay County")
    assert route.calls.last.request.url.params["district_code"] == "630"
    assert isinstance(out, gpd.GeoDataFrame)
    assert out["district_code"].tolist() == ["630"]
    assert out["boundary_type"].tolist() == ["unified"]


def test_school_zone_status_returns_one_row_per_school(api):
    api.get(url("datasets", "school_attendance_zones", "school_status")).mock(
        return_value=recorded("m/stat/g/d/school_attendance_zones/school_status-7e2608.json")
    )
    out = gcd.school_zone_status(district_code="630")
    assert list(out.columns) == STATUS_COLUMNS
    assert str(out["year"].dtype) == "Int64"
    assert (out["district_code"] == "630").all()
    assert "zoned" in gcd.meta(out)["note"]


def test_school_zone_status_keeps_exact_school_pairs_and_empty_results(api, tables):
    def respond(request):
        if request.url.params.get("zone_status") == "no_zone":
            return json_response({"data": [], "count": 0, "note": "n"})
        return json_response(
            {
                "data": [
                    {
                        "year": 2027,
                        "district_code": "660",
                        "school_code": "0191",
                        "zone_status": "zoned",
                    },
                    {
                        "year": 2027,
                        "district_code": "660",
                        "school_code": "9999",
                        "zone_status": "zoned",
                    },
                ],
                "count": 2,
                "note": "n",
            }
        )

    api.get(url("datasets", "school_attendance_zones", "school_status")).mock(side_effect=respond)
    out = gcd.school_zone_status(school="Roswell High School")
    assert out["school_code"].tolist() == ["0191"]
    empty = gcd.school_zone_status(zone_status="no_zone")
    assert len(empty) == 0
    assert list(empty.columns) == STATUS_COLUMNS


def test_school_zone_coverage_pivots_the_per_level_columns_long(api, tables):
    api.get(url("datasets", "school_attendance_zones", "coverage")).mock(
        return_value=recorded("coverage.json")
    )
    out = gcd.school_zone_coverage(district_code=["601", "630"])
    assert gcd.school_zone_coverage(district="Clay County")["district_code"].unique().tolist() == [
        "630"
    ]
    assert len(out) == 6
    assert list(out.columns[:13]) == [
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
    ]
    assert not any(c.endswith(("_elementary", "_middle", "_high")) for c in out.columns)
    assert out["zone_level"].tolist() == ["elementary", "middle", "high"] * 2
    assert str(out["zone_count"].dtype) == "Int64"
    clay_high = out[(out["district_code"] == "630") & (out["zone_level"] == "high")]
    assert clay_high["level_status"].tolist() == ["served_by_other_district"]
    assert clay_high["served_elsewhere"].iloc[0][0]["district_code"] == "720"
    assert out["served_elsewhere"].iloc[0] == []
    assert "Not an official" in gcd.meta(out)["note"]
    assert len(gcd.school_zone_coverage()) == 9


def test_school_zone_coverage_with_geometry_keeps_the_outlines(api):
    gpd = pytest.importorskip("geopandas")
    api.get(url("datasets", "school_attendance_zones", "coverage")).mock(
        return_value=recorded("coverage.geojson")
    )
    out = gcd.school_zone_coverage(district_code="630", geometry=True)
    assert isinstance(out, gpd.GeoDataFrame)
    assert len(out) == 3
    assert out.geometry.name == "geometry"
    assert out["served_elsewhere"].iloc[2][0]["school_code"] == "0201"


def test_served_for_level_reads_json_text():
    text = '[{"zone_level": "high", "district_code": "720", "school_code": "0201", "reason": "r"}]'
    assert served_for_level(text, "high") == [
        {"district_code": "720", "school_code": "0201", "reason": "r"}
    ]
    assert served_for_level(text, "middle") == []
    assert served_for_level(None, "high") == []
