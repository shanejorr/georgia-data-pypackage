from __future__ import annotations

import json
import re

import httpx
import pandas as pd
import pytest

import georgiacivicdata as gcd
from georgiacivicdata import _geocode
from georgiacivicdata._geocode import (
    address_input,
    census_csv,
    census_geocode,
    parse_census,
    paste_address,
)
from helpers import fixture_json, json_response, url

CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
CENSUS_TEXT = "\n".join(
    [
        '"1","55 Trinity Ave SW, Atlanta, GA, 30303","Match","Exact","55 TRINITY AVE SW, ATLANTA, GA, 30303","-84.390279998653,33.747923442489","17344323","R"',
        '"0","206 Washington St SW, Atlanta, GA 30334, , , ","Match","Non_Exact","206 WASHINGTON ST SW, ATLANTA, GA, 30334","-84.388565089734,33.74979815619","17344749","L"',
        '"2","1 Nowhere Blvd, Nocity, GA, ","No_Match"',
        '"3","10 Main St, Somewhere, GA, ","Tie"',
    ]
)


def test_address_input_takes_one_line_addresses_or_a_data_frame():
    one = address_input(["206 Washington St SW, Atlanta, GA 30334", " ", None])
    assert one.street == ["206 Washington St SW, Atlanta, GA 30334", None, None]
    assert one.city == [None, None, None]
    assert address_input("206 Washington St SW").street == ["206 Washington St SW"]
    df = pd.DataFrame(
        {
            "street": ["206 Washington St SW", None],
            "city": "Atlanta",
            "state": "GA",
            "zip": ["30334", ""],
        }
    )
    two = address_input(df)
    assert two.address == ["206 Washington St SW, Atlanta, GA 30334", None]
    assert two.zip == ["30334", None]
    as_dict = address_input({"street": ["1 A St"], "city": [None], "state": ["GA"], "zip": [None]})
    assert as_dict.address == ["1 A St, GA"]
    assert paste_address("1 A St", None, "GA", None) == "1 A St, GA"
    assert paste_address(None, "x", "y", "z") is None
    with pytest.raises(ValueError, match=r"missing: city, state, zip"):
        address_input(pd.DataFrame({"street": ["x"]}))
    with pytest.raises(ValueError, match="no rows"):
        address_input(pd.DataFrame({"street": [], "city": [], "state": [], "zip": []}))
    with pytest.raises(TypeError, match="`address` must be"):
        address_input(1)
    with pytest.raises(TypeError, match="`address` must be"):
        address_input([1, 2])


def test_address_input_reads_polars():
    pl = pytest.importorskip("polars")
    df = pl.DataFrame(
        {"street": ["2 E Bay St"], "city": ["Savannah"], "state": ["GA"], "zip": ["31401"]}
    )
    assert address_input(df).address == ["2 E Bay St, Savannah, GA 31401"]


def test_census_csv_quotes_every_field():
    rows = address_input(
        pd.DataFrame(
            {"street": ['A "B" St, Suite 1'], "city": [None], "state": ["GA"], "zip": [None]}
        )
    )
    assert census_csv([0], rows) == '"0","A ""B"" St, Suite 1","","GA",""\n'


def test_parse_census_reads_matches_misses_and_ties():
    out = parse_census(CENSUS_TEXT)
    assert list(out) == ["1", "0", "2", "3"]
    assert [g.match_status for g in out.values()] == ["match", "match", "no_match", "tie"]
    assert [g.match_type for g in out.values()] == ["exact", "non_exact", None, None]
    assert out["1"].lat == 33.747923442489
    assert out["0"].lon == -84.388565089734
    assert out["2"].lat is None
    assert parse_census("") == {}
    assert parse_census('"5","x","Match","Exact","x","bad"')["5"].lat is None


def test_census_geocode_uploads_a_batch_and_joins_results_back_by_id(api):
    route = api.post(CENSUS).mock(return_value=httpx.Response(200, text=CENSUS_TEXT))
    addresses = address_input(
        [
            "206 Washington St SW, Atlanta, GA 30334",
            "55 Trinity Ave SW, Atlanta, GA 30303",
            "1 Nowhere Blvd, Nocity, GA",
            "10 Main St, Somewhere, GA",
            None,
        ]
    )
    out = census_geocode(addresses)
    assert route.call_count == 1
    request = route.calls.last.request
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert b'name="benchmark"' in request.content
    assert b"Public_AR_Current" in request.content
    assert [g.match_status for g in out] == ["match", "match", "no_match", "tie", None]
    assert out[0].lat == 33.74979815619
    assert out[1].matched_address == "55 TRINITY AVE SW, ATLANTA, GA, 30303"


def test_large_address_lists_are_split_into_census_sized_batches(api, monkeypatch):
    monkeypatch.setattr(_geocode, "CENSUS_BATCH_MAX", 2)
    sizes = []

    def respond(request):
        text = request.content.decode()
        ids = re.findall(r'^"(\d+)","Address', text, flags=re.MULTILINE)
        sizes.append(len(ids))
        return httpx.Response(200, text="\n".join(f'"{i}","x","No_Match"' for i in ids))

    api.post(CENSUS).mock(side_effect=respond)
    out = census_geocode(address_input([f"Address {i}" for i in range(1, 6)]))
    assert sizes == [2, 2, 1]
    assert [g.match_status for g in out] == ["no_match"] * 5


def test_locate_with_addresses_geocodes_locally_then_sends_points_only(api, tables):
    sent = {}
    api.post(CENSUS).mock(return_value=httpx.Response(200, text=CENSUS_TEXT))

    def respond(request):
        sent.update(json.loads(request.content))
        result = fixture_json("locate-capitol.json")
        return json_response({"results": [{**result, "id": p["id"]} for p in sent["points"]]})

    api.post(url("locate")).mock(side_effect=respond)
    with pytest.warns(gcd.GCDAdvisory):
        out = gcd.locate(
            address=[
                "206 Washington St SW, Atlanta, GA 30334",
                "55 Trinity Ave SW, Atlanta, GA 30303",
                "1 Nowhere Blvd, Nocity, GA",
                "10 Main St, Somewhere, GA",
                "",
            ],
            id=["capitol", "city_hall", "nowhere", "tie", "blank"],
        )
    assert list(out.columns) == [
        "id",
        "address",
        "match_status",
        "match_type",
        "matched_address",
        "lat",
        "lon",
        "geographic_type",
        "geographic_id",
        "geographic_name",
        "grades",
        "note",
    ]
    assert [p["id"] for p in sent["points"]] == ["1", "2"]
    assert "Washington" not in json.dumps(sent)
    assert "Trinity" not in json.dumps(sent)
    assert out["id"].unique().tolist() == ["capitol", "city_hall", "nowhere", "tie", "blank"]
    assert out.loc[out["id"].isin(["nowhere", "tie", "blank"]), "note"].tolist() == [
        "The U.S. Census geocoder found no match for this address.",
        "The U.S. Census geocoder found more than one possible match for this address.",
        "No address was given.",
    ]


def test_a_census_failure_is_an_error_that_never_echoes_the_address(api):
    api.post(CENSUS).mock(return_value=httpx.Response(500))
    with pytest.raises(gcd.GCDCensusError) as info:
        gcd.locate(address="206 Washington St SW, Atlanta, GA 30334")
    assert (
        str(info.value)
        == "The U.S. Census geocoder returned an error (HTTP 500).\n  Try again later."
    )
    assert isinstance(info.value, gcd.GCDUnavailableError)
    api.post(CENSUS).mock(side_effect=httpx.ReadTimeout("timeout"))
    with pytest.raises(gcd.GCDUnavailableError) as info:
        gcd.locate(address="206 Washington St SW, Atlanta, GA 30334")
    assert "Washington" not in str(info.value)
