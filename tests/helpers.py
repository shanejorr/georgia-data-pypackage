"""Shared test helpers.

Tests pass offline: every HTTP request goes through ``respx``, and a request
no route matches fails the test. Recorded API responses live in
``tests/fixtures/m/`` (recorded once from the production API for the R
package; see CLAUDE.md before re-recording).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa

from georgiacivicdata import _cache
from georgiacivicdata._api import BASE_URL, build_url

FIXTURES = Path(__file__).parent / "fixtures"
LIVE = os.environ.get("GCD_LIVE_TESTS") == "true"

LOOKUP_TABLES = ("districts", "schools", "block_groups", "counties", "demographics", "tracts")


def fixture_path(rel: str) -> Path:
    return FIXTURES / rel


def fixture_json(rel: str) -> Any:
    return json.loads(fixture_path(rel).read_text(encoding="utf-8"))


def recorded(rel: str, status: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    """A recorded response: JSON for ``.json`` files, text otherwise."""
    path = fixture_path(rel)
    content_type = "application/json" if path.suffix == ".json" else "text/plain"
    if path.suffix == ".geojson":
        content_type = "application/geo+json"
    return httpx.Response(
        status,
        content=path.read_bytes(),
        headers={"content-type": content_type, **(headers or {})},
    )


def json_response(
    body: Any, status: int = 200, headers: dict[str, str] | None = None
) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers)


def error_response(
    status: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return json_response(
        {"error": {"code": code, "message": message, "details": details}},
        status=status,
        headers=headers,
    )


def url(*path: str) -> str:
    return BASE_URL + "/" + "/".join(path)


def seed_meta(path: str | list[str], value: Any, query: dict[str, list[str]] | None = None) -> None:
    """Put a parsed JSON value into the session cache under its URL."""
    _cache.STATE.meta["json:" + build_url(path, query)] = value


def seed_recorded(rel: str, path: str | list[str]) -> None:
    """A recorded schema, read from a fixture file, put in the session cache."""
    seed_meta(path, fixture_json(rel))


def seed_grad_schema() -> None:
    seed_recorded(
        "m/desc/g/d/graduation_rate_4_year_cohort.json",
        ["datasets", "graduation_rate_4_year_cohort"],
    )


def make_tables() -> dict[str, pa.Table]:
    """Small lookup tables for the resolver and locate() (public names and
    codes; no addresses)."""
    return {
        "districts": pa.table(
            {
                "district_code": [
                    "660",
                    "761",
                    "630",
                    "634",
                    "638",
                    "644",
                    "7830613",
                    "9901",
                    "9902",
                ],
                "district_name": [
                    "Fulton County",
                    "Atlanta Public Schools",
                    "Clay County",
                    "Coffee County",
                    "Coweta County",
                    "DeKalb County",
                    "BIA Charter School",
                    "Sample Academy",
                    "Other Academy",
                ],
                "former_names": [
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "Brookhaven Innovation Academy",
                    None,
                    "Sample Academy",
                ],
                "county_fips": [
                    "13121",
                    "13121",
                    "13061",
                    "13069",
                    "13077",
                    "13089",
                    "13135",
                    "13121",
                    "13121",
                ],
                "active": [True, True, True, True, True, True, True, True, False],
            }
        ),
        "schools": pa.table(
            {
                "district_code": [
                    "660",
                    "660",
                    "660",
                    "660",
                    "634",
                    "638",
                    "630",
                    "761",
                    "761",
                    "644",
                ],
                "school_code": [
                    "0191",
                    "0106",
                    "2060",
                    "3066",
                    "0282",
                    "2052",
                    "0104",
                    "0199",
                    "4560",
                    "0101",
                ],
                "school_name": [
                    "Roswell High School",
                    "Milton High School",
                    "Milton High School",
                    "Riverwood International Charter School",
                    "Eastside Elementary School",
                    "Eastside Elementary School",
                    "Clay County Middle School",
                    "Centennial Academy (Charter)",
                    "Midtown High School",
                    "Jos\u00e9 Mart\u00ed Academy",
                ],
                "former_names": [
                    None,
                    None,
                    None,
                    "Riverwood High School",
                    None,
                    None,
                    None,
                    None,
                    "Henry W. Grady High School",
                    None,
                ],
                "active": [True, True, False, True, True, True, True, True, True, True],
            }
        ),
        "counties": pa.table(
            {
                "county_fips": ["13001", "13061", "13089", "13121"],
                "county_name": ["Appling", "Clay", "DeKalb", "Fulton"],
            }
        ),
        "tracts": pa.table(
            {
                "tract_geoid": ["13121003500"],
                "tract_name": ["Census Tract 35"],
                "county_fips": ["13121"],
            }
        ),
        "block_groups": pa.table(
            {
                "block_group_geoid": ["131210035001"],
                "block_group_name": ["Block Group 1, Census Tract 35, Fulton County"],
            }
        ),
    }
