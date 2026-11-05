from __future__ import annotations

import pytest

import georgiacivicdata as gcd
from georgiacivicdata._params import Places
from georgiacivicdata._places import levenshtein, near_names, normalize_place, resolve_places
from helpers import error_response, json_response, url


def test_normalize_place_ignores_case_accents_spacing_and_county():
    assert [
        normalize_place(x) for x in (" Fulton County ", "FULTON", "fulton  county", "DeKalb")
    ] == [
        "fulton",
        "fulton",
        "fulton",
        "dekalb",
    ]
    # precomposed and decomposed accents, curly apostrophes
    assert normalize_place("Jos\u00e9 Mart\u00ed") == "jose marti"
    assert normalize_place("Jose\u0301 Marti\u0301") == "jose marti"
    assert normalize_place("O\u2019Neal") == "o'neal"
    assert normalize_place("\u00c5ngstr\u00f6m \u0141\u00f3d\u017a") == "angstrom lodz"
    # only a trailing "County" is dropped
    assert normalize_place("County Line Elementary") == "county line elementary"


def test_district_and_county_names_resolve_to_codes(tables):
    out = resolve_places(district=["fulton", "Atlanta Public Schools"], county="DeKalb County")
    assert out.district_code == ["660", "761"]
    assert out.county_fips == ["13089"]
    assert out.school_pairs is None
    assert resolve_places() == Places()


def test_former_names_match(tables):
    assert resolve_places(district="Brookhaven Innovation Academy").district_code == ["7830613"]
    out = resolve_places(school="Riverwood High School", district="Fulton County")
    assert out.school_pairs == ["660-3066"]


def test_school_names_resolve_to_district_school_pairs(tables):
    out = resolve_places(school="Roswell High School")
    assert out.school_pairs == ["660-0191"]
    assert out.district_code is None
    out = resolve_places(
        school="Eastside Elementary School", district=["Coffee County", "Coweta County"]
    )
    assert out.school_pairs == ["634-0282", "638-2052"]
    out = resolve_places(school="jose marti academy", filters={"district_code": ["644"]})
    assert out.school_pairs == ["644-0101"]


def test_ambiguous_names_stop_with_the_candidates(tables):
    with pytest.raises(gcd.GCDPlaceAmbiguousError) as info:
        resolve_places(school="Eastside Elementary School")
    assert str(info.value) == (
        "'Eastside Elementary School' names schools in 2 districts.\n"
        "  Add `district` (or `district_code`) to pick one.\n"
        "  * 634-0282: Eastside Elementary School (Coffee County, active)\n"
        "  * 638-2052: Eastside Elementary School (Coweta County, active)"
    )
    assert info.value.code == "PLACE_AMBIGUOUS"
    assert len(info.value.details["candidates"]) == 2
    with pytest.raises(gcd.GCDPlaceAmbiguousError) as info:
        resolve_places(school="Milton High School", district="Fulton")
    assert str(info.value) == (
        "'Milton High School' matches more than one school.\n"
        "  Use `school_id` with one 'DISTRICT-SCHOOL' code.\n"
        "  * 660-0106: Milton High School (Fulton County, active)\n"
        "  * 660-2060: Milton High School (Fulton County, inactive)"
    )
    with pytest.raises(gcd.GCDPlaceAmbiguousError) as info:
        resolve_places(district="Sample Academy")
    assert str(info.value) == (
        "'Sample Academy' matches more than one district.\n"
        "  Use `district_code` with one of these codes.\n"
        "  * 9901: Sample Academy\n"
        "  * 9902: Other Academy"
    )


def test_unknown_names_stop_with_suggestions(tables, api):
    api.get(url("dimensions", "districts", "rows")).mock(return_value=json_response({"data": []}))
    api.get(url("dimensions", "schools", "rows")).mock(
        return_value=json_response({"data": [{"school_name": "Roswell High School"}]})
    )
    with pytest.raises(gcd.GCDPlaceNotFoundError) as info:
        resolve_places(district="Fultn County")
    assert str(info.value) == (
        "No district named 'Fultn County'.\n"
        "  Did you mean: 'Fulton County'?\n"
        "  Names match exactly (ignoring case and accents); browse with "
        "gcd.dimension('districts', q='fultn')."
    )
    assert info.value.details["suggestions"] == ["Fulton County"]
    with pytest.raises(gcd.GCDPlaceNotFoundError) as info:
        resolve_places(school="Roswell High", district="Fulton County")
    assert str(info.value).splitlines()[:2] == [
        "No school named 'Roswell High' in Fulton County (660).",
        "  Did you mean: 'Roswell High School'?",
    ]
    with pytest.raises(gcd.GCDPlaceNotFoundError) as info:
        resolve_places(school="Midtown High School", district="Fulton County")
    assert str(info.value).splitlines()[:2] == [
        "No school named 'Midtown High School' in Fulton County (660).",
        "  A school with that name is in Atlanta Public Schools (761).",
    ]


def test_a_failed_suggestion_search_still_gives_the_not_found_error(tables, api):
    api.get(url("dimensions", "counties", "rows")).mock(
        return_value=error_response(500, "INTERNAL_ERROR", "boom")
    )
    with pytest.raises(gcd.GCDPlaceNotFoundError) as info:
        resolve_places(county="Nowhere")
    assert str(info.value) == (
        "No county named 'Nowhere'.\n"
        "  Names match exactly (ignoring case and accents); browse with "
        "gcd.dimension('counties', q='nowhere')."
    )


def test_a_code_and_a_name_for_the_same_place_is_an_error(tables):
    with pytest.raises(ValueError, match="Give `district` or `district_code`, not both"):
        resolve_places(district="Fulton", filters={"district_code": ["660"]})
    with pytest.raises(ValueError, match="Give `county` or `county_fips`, not both"):
        resolve_places(county="Fulton", filters={"county_fips": ["13121"]})
    with pytest.raises(ValueError, match="Give `school` or `school_id`, not both"):
        resolve_places(school="Roswell High School", filters={"school": ["660-0191"]})


def test_a_name_argument_needs_its_code_column_in_the_target():
    with pytest.raises(gcd.GCDError) as info:
        resolve_places(
            school="Roswell High School",
            columns=["year", "county_fips"],
            target='the dataset "employment"',
        )
    assert str(info.value) == (
        '`school` doesn\'t apply: the dataset "employment" has no district_code or '
        "school_code columns.\n  Check the columns with gcd.columns()."
    )
    assert info.value.code == "PLACE_NOT_APPLICABLE"
    with pytest.raises(TypeError, match="`district` must be a string"):
        resolve_places(district=1)
    with pytest.raises(TypeError, match="`district` must be a string"):
        resolve_places(district=[])


def test_near_names_suggests_close_spellings_only(tables):
    assert near_names("Fultn County", "districts", "district_name") == ["Fulton County"]
    assert near_names("Zzzzzzzz", "districts", "district_name") == []
    assert near_names("Rosewell High School", "schools", "school_name", districts=["660"]) == [
        "Roswell High School"
    ]
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3
