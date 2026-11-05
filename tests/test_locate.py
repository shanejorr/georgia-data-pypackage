from __future__ import annotations

import copy
import json
import warnings

import pandas as pd
import pytest

import georgiacivicdata as gcd
from georgiacivicdata._locate import (
    format_grades,
    level_note,
    locate_points,
    locate_rows,
    overlapping_zones,
    reason_for_level,
)
from helpers import fixture_json, json_response, make_tables, recorded, url

CAPITOL = fixture_json("locate-capitol.json")


def capitol():
    return copy.deepcopy(CAPITOL)


def lookups():
    t = make_tables()
    return {
        "counties": dict(
            zip(t["counties"]["county_fips"].to_pylist(), t["counties"]["county_name"].to_pylist())
        ),
        "tracts": dict(
            zip(t["tracts"]["tract_geoid"].to_pylist(), t["tracts"]["tract_name"].to_pylist())
        ),
        "block_groups": dict(
            zip(
                t["block_groups"]["block_group_geoid"].to_pylist(),
                t["block_groups"]["block_group_name"].to_pylist(),
            )
        ),
    }


def col(rows, name):
    return [r[name] for r in rows]


def test_format_grades_writes_short_grade_ranges():
    assert [
        format_grades(lo, hi)
        for lo, hi in zip(["k", "pk", "06", "09", "k", None], ["05", "05", "08", "12", "k", "05"])
    ] == ["K-5", "PK-5", "6-8", "9-12", "K", None]
    assert format_grades("x", "05") is None


def test_overlapping_zones_finds_schools_whose_grade_runs_intersect():
    assert overlapping_zones(["k", "03"], ["02", "05"], ["a", "b"]) == [False, False]
    assert overlapping_zones(["k", "k"], ["05", "05"], ["a", "b"]) == [True, True]
    assert overlapping_zones(["k", "k"], ["05", "05"], ["a", "a"]) == [False, False]


def test_reason_for_level_quotes_one_levels_part_of_a_reason():
    r = "Elementary: No map. More text. Middle: Two schools share it."
    assert reason_for_level(r, "middle") == "Middle: Two schools share it."
    assert reason_for_level(r, "elementary") == "Elementary: No map. More text."
    assert reason_for_level(r, "high") is None
    assert reason_for_level("Plain.", "high") == "Plain."
    assert reason_for_level(None, "high") is None
    assert reason_for_level("Lead. High: x", "middle") == "Lead."


def test_locate_rows_lays_out_one_points_places():
    out = locate_rows(capitol(), lookups())
    assert col(out, "geographic_type") == [
        "county",
        "tract",
        "block_group",
        "school_district",
        "elementary_school",
        "middle_school",
        "high_school",
    ]
    assert col(out, "geographic_id") == [
        "13121",
        "13121003500",
        "131210035001",
        "761",
        "761-0199",
        "761-0199",
        "761-4560",
    ]
    assert col(out, "geographic_name")[:4] == [
        "Fulton",
        "Census Tract 35",
        "Block Group 1, Census Tract 35, Fulton County",
        "Atlanta Public Schools",
    ]
    assert col(out, "grades") == [None, None, None, None, "K-5", "6-8", "9-12"]
    assert all(n is None for n in col(out, "note"))


def test_levels_without_a_zone_get_a_row_with_a_note():
    r = capitol()
    r["zones"] = r["zones"][:1]
    r["level_status"] = {
        "elementary": "zoned",
        "middle": "not_available",
        "high": "served_by_other_district",
    }
    r["coverage_reason"] = "Middle: No map is published."
    r["served_elsewhere"] = [
        {
            "zone_level": "high",
            "district_code": "720",
            "school_code": "0201",
            "reason": "Clay County operates no high school.",
        }
    ]
    out = locate_rows(r, lookups())
    assert col(out, "geographic_type")[4:] == ["elementary_school", "middle_school", "high_school"]
    assert col(out, "geographic_id")[5:] == [None, None]
    assert col(out, "note")[5:] == [
        "No middle school zone has been collected for this district yet. Middle: No map is published.",
        "Clay County operates no high school.",
    ]
    r["level_status"] = {"elementary": "zoned", "middle": "gap", "high": "served_by_other_district"}
    r["coverage_reason"] = None
    r["served_elsewhere"] = [{"zone_level": "high", "district_code": "720"}]
    out = locate_rows(r, lookups())
    assert col(out, "note")[5:] == [
        "This point lies in no middle school zone.",
        "High students here are served by district 720.",
    ]
    assert (
        level_note("high", "served_by_other_district", {})
        == "High students here are served by another district."
    )
    assert level_note("high", "partial", {}) == "High school zone status: partial."


def test_department_of_defense_districts_and_warnings_are_noted():
    r = capitol()
    r["district"] = {
        "district_code": None,
        "district_name": "Fort Benning Schools",
        "boundary_type": "dodea",
    }
    r["coverage_reason"] = (
        "Department of Defense (DoDEA) schools serve this area; they are not Georgia public "
        "school districts and publish no zones."
    )
    r["zones"] = []
    r["level_status"] = {"elementary": "not_available"}
    out = locate_rows(r, lookups())
    district = next(x for x in out if x["geographic_type"] == "school_district")
    assert district["geographic_id"] is None
    assert district["geographic_name"] == "Fort Benning Schools"
    assert district["note"].startswith("Department of Defense")
    elementary = next(x for x in out if x["geographic_type"] == "elementary_school")
    assert "DoDEA" in elementary["note"]

    r = capitol()
    r["zones"][2]["currency_status"] = "stale_known_changes"
    r["currency_warning"] = "A change is pending."
    r["zones"][1]["zone_level"] = "elementary"
    r["zones"][1]["school_code"] = "0200"
    r["zones"][1]["grade_low"] = "k"
    r["overlap_warning"] = "Two zones overlap."
    out = locate_rows(r, lookups())
    assert [x["note"] for x in out if x["geographic_type"] == "high_school"] == [
        "A change is pending."
    ]
    assert [x["note"] for x in out if x["geographic_type"] == "elementary_school"] == [
        "Two zones overlap."
    ] * 2


def test_failures_give_one_row_with_the_reason():
    err = {"id": "1", "error": {"code": "INVALID_COORDINATES", "message": "lat/lon out of range"}}
    assert col(locate_rows(err, {}), "note") == [
        "The API couldn't locate this point: lat/lon out of range."
    ]
    assert col(locate_rows({"coverage_status": "outside_georgia"}, {}), "note") == [
        "The point is outside Georgia."
    ]
    r = {
        "coverage_status": "not_zoned",
        "coverage_reason": "No zone serves pre-K.",
        "district": {"district_code": "761", "district_name": "Atlanta Public Schools"},
    }
    assert col(locate_rows(r, {}), "note") == ["No zone serves pre-K."]
    assert col(locate_rows({"coverage_status": "gap"}, {}), "note") == [
        "No place was found for this point."
    ]


def test_locate_locates_points_in_one_post(api, tables):
    def respond(request):
        body = json.loads(request.content)
        if len(body["points"]) == 3:
            return recorded("m/loc/g/locate-84eb20-POST.json")
        return recorded("m/loc/g/locate-49c9b2-POST.json")

    route = api.post(url("locate")).mock(side_effect=respond)
    with pytest.warns(gcd.GCDAdvisory, match="default assignment"):
        out = gcd.locate(lat=[33.749, 36.1627, 200], lon=[-84.388, -86.7816, 0])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        again = gcd.locate(lat=33.749, lon=-84.388, id="capitol", grade="9")
    assert list(out.columns) == [
        "id",
        "lat",
        "lon",
        "geographic_type",
        "geographic_id",
        "geographic_name",
        "grades",
        "note",
    ]
    assert out["id"].tolist() == [0] * 7 + [1, 2]
    assert out["note"].tolist()[7:] == [
        "The point is outside Georgia.",
        "The API couldn't locate this point: lat/lon out of range.",
    ]
    assert "default assignment" in gcd.meta(out)["assignment_note"]
    assert again["id"].tolist() == ["capitol"] * 5
    assert again["geographic_type"].iloc[4] == "high_school"
    body = json.loads(route.calls.last.request.content)
    assert body["grade"] == "09"
    assert "33.749" not in str(route.calls.last.request.url)


def test_locate_sends_batches_and_checks_the_echoed_ids(api, capsys):
    bodies = []

    def respond(request):
        body = json.loads(request.content)
        bodies.append(body)
        return json_response(
            {
                "results": [
                    {
                        "id": p["id"],
                        "coverage_status": "outside_georgia",
                        "assignment_note": "A zone is the default assignment.",
                        "note": "Not official.",
                    }
                    for p in body["points"]
                ]
            }
        )

    api.post(url("locate")).mock(side_effect=respond)
    out = locate_points([1, 2, 3], [4, 5, 6], batch_size=2, grade="05", year="2027")
    assert len(bodies) == 2
    assert [p["id"] for p in bodies[0]["points"]] == ["1", "2"]
    assert bodies[1]["points"][0]["id"] == "3"
    assert bodies[0]["grade"] == "05"
    assert bodies[0]["year"] == 2027
    assert len(out) == 3

    with pytest.warns(gcd.GCDAdvisory):
        res = gcd.locate(lat=[31, None], lon=[-83, -84])
    assert res["note"].tolist() == ["The point is outside Georgia.", "No coordinates were given."]
    assert gcd.meta(res)["note"] == "Not official."
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        gcd.locate(lat=31, lon=-83)


def test_locate_refuses_mismatched_ids(api):
    api.post(url("locate")).mock(return_value=json_response({"results": [{"id": "9"}]}))
    with pytest.raises(gcd.GCDError, match="didn't match the points sent") as info:
        gcd.locate(lat=31, lon=-83)
    assert info.value.code == "LOCATE_MISMATCH"


def test_locate_as_polars_with_numpy_input(api, tables):
    pl = pytest.importorskip("polars")
    import numpy as np

    api.post(url("locate")).mock(
        return_value=json_response({"results": [{**capitol(), "id": "1"}]})
    )
    out = gcd.locate(lat=np.array([33.749]), lon=pd.Series([-84.388]), quiet=True, backend="polars")
    assert isinstance(out, pl.DataFrame)
    assert out.schema["lat"] == pl.Float64
    assert out["geographic_type"].to_list()[0] == "county"


def test_locate_checks_its_inputs():
    with pytest.raises(ValueError, match=r"Give `lat` and `lon`, or `address`\."):
        gcd.locate()
    with pytest.raises(ValueError, match="not both"):
        gcd.locate(lat=1, lon=2, address="x")
    with pytest.raises(ValueError, match="same length"):
        gcd.locate(lat=[1, 2], lon=1)
    with pytest.raises(TypeError, match="numbers"):
        gcd.locate(lat="33", lon="-84")
    with pytest.raises(ValueError, match="Give both"):
        gcd.locate(lat=1)
    with pytest.raises(ValueError, match=r"`id` must have one value per input \(1\)"):
        gcd.locate(lat=1, lon=2, id=[1, 2])
    with pytest.raises(ValueError, match="`grade` must be one of"):
        gcd.locate(lat=1, lon=2, grade="13")
