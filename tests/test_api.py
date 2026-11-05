from __future__ import annotations

import re
import time

import httpx
import pytest

import georgiacivicdata as gcd
from georgiacivicdata import _api, _cache
from georgiacivicdata._api import BASE_URL, build_url, get_json, path_segment, perform
from helpers import error_response, json_response, url


def test_user_agent_names_the_package_and_repository():
    assert re.fullmatch(
        r"georgiacivicdata-py/[0-9.]+ \(\+https://github\.com/shanejorr/georgia-data-pypackage\)",
        _api.user_agent(),
    )


def test_build_url_joins_lists_with_commas():
    out = build_url(
        ["datasets", "employment", "rows"],
        {"county_fips": ["13121", "13089"], "year": ["2024"]},
    )
    assert out == BASE_URL + "/datasets/employment/rows?county_fips=13121,13089&year=2024"
    assert build_url("datasets", {"q": ["a b,c"]}) == BASE_URL + "/datasets?q=a%20b%2Cc"


def test_path_segment_escapes_names():
    assert path_segment("a b/c") == "a%20b%2Fc"


def test_requests_send_the_user_agent(api):
    route = api.get(url("datasets")).mock(return_value=json_response({"data": []}))
    get_json("datasets")
    assert route.calls.last.request.headers["user-agent"] == _api.user_agent()


def test_retry_after_reads_seconds_and_dates():
    assert _api.retry_after({"retry-after": "7"}) == 7
    assert _api.retry_after({}) is None
    assert _api.retry_after({"retry-after": "soon"}) is None
    future = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() + 30))
    assert 0 < _api.retry_after({"retry-after": future}) <= 31


def test_429_and_gateway_errors_are_retried(api, capsys, monkeypatch):
    waits = []
    monkeypatch.setattr(_api, "_sleep", waits.append)
    route = api.get(url("datasets")).mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "7"}),
            httpx.Response(503),
            json_response({"data": []}),
        ]
    )
    assert get_json("datasets") == {"data": []}
    assert route.call_count == 3
    assert waits[0] == 7
    err = capsys.readouterr().err
    assert "The API's rate limit was reached; retrying in 7 seconds." in err
    assert "The server is busy (HTTP 503); retrying shortly." in err


def test_retry_notes_are_quiet_when_asked(api, capsys):
    api.get(url("datasets")).mock(side_effect=[httpx.Response(502), json_response({})])
    with gcd.option_context(quiet=True):
        get_json("datasets")
    assert capsys.readouterr().err == ""


def test_retries_stop_after_four_tries(api):
    route = api.get(url("datasets", "slow", "rows")).mock(
        return_value=error_response(503, "QUERY_TIMEOUT", "The query took too long")
    )
    with pytest.raises(gcd.GCDUnavailableError) as info:
        get_json(["datasets", "slow", "rows"])
    assert route.call_count == 4
    assert info.value.code == "QUERY_TIMEOUT"
    assert info.value.status == 503
    assert str(info.value) == (
        "The Georgia Civic Data API couldn't answer (HTTP 503).\n"
        "  The query took too long\n"
        "  Try again in a few minutes."
    )


def test_a_500_is_not_retried(api):
    route = api.get(url("datasets")).mock(
        return_value=error_response(500, "INTERNAL_ERROR", "boom")
    )
    with pytest.raises(gcd.GCDUnavailableError):
        get_json("datasets")
    assert route.call_count == 1


@pytest.mark.parametrize(
    ("path", "response", "cls", "code", "message"),
    [
        (
            ["datasets", "graduation_rate", "rows"],
            error_response(
                404,
                "TOPIC_NOT_FOUND",
                "No dataset 'graduation_rate'",
                {"did_you_mean": ["ccrpi_graduation_rate", "graduation_rate_4_year_cohort"]},
            ),
            gcd.GCDNotFoundError,
            "TOPIC_NOT_FOUND",
            "No dataset 'graduation_rate'\n"
            "  Did you mean: 'ccrpi_graduation_rate', 'graduation_rate_4_year_cohort'?",
        ),
        (
            ["datasets", "counties", "contract"],
            error_response(
                404,
                "TOPIC_NOT_FOUND",
                "No dataset 'counties'",
                {"hint": "'counties' is a lookup table: /api/v1/dimensions/counties"},
            ),
            gcd.GCDNotFoundError,
            "TOPIC_NOT_FOUND",
            "No dataset 'counties'\n  'counties' is a lookup table: /api/v1/dimensions/counties",
        ),
        (
            ["dimensions", "countys"],
            error_response(
                404,
                "DIM_NOT_FOUND",
                "No lookup table 'countys'",
                {"available": ["counties", "tracts"]},
            ),
            gcd.GCDNotFoundError,
            "DIM_NOT_FOUND",
            "No lookup table 'countys'\n  Available: 'counties', 'tracts'.",
        ),
        (
            ["old", "path"],
            error_response(404, "NOT_FOUND", "Gone", {"moved_to": "/api/v1/datasets"}),
            gcd.GCDNotFoundError,
            "NOT_FOUND",
            "Gone\n  Moved to /api/v1/datasets.",
        ),
        (
            ["locate"],
            error_response(
                400,
                "INVALID_GRADE",
                "unknown grade; use pk, k or 01-12",
                {"valid": ["pk", "k", "01"]},
            ),
            gcd.GCDError,
            "INVALID_GRADE",
            "unknown grade; use pk, k or 01-12\n  Valid values: 'pk', 'k', '01'.",
        ),
        (
            ["datasets", "busy", "rows"],
            error_response(
                429, "RATE_LIMITED", "Too many requests", headers={"retry-after": "500"}
            ),
            gcd.GCDUnavailableError,
            "RATE_LIMITED",
            "The Georgia Civic Data API's rate limit was reached.\n  Try again in 500 seconds.",
        ),
        (
            ["datasets", "html", "rows"],
            httpx.Response(504, headers={"content-type": "text/html"}, content=b"<html>Bad</html>"),
            gcd.GCDUnavailableError,
            "HTTP_504",
            "The Georgia Civic Data API couldn't answer (HTTP 504).\n"
            "  Gateway Timeout\n"
            "  Try again in a few minutes.",
        ),
    ],
)
def test_api_error_envelopes_become_exceptions(api, path, response, cls, code, message):
    api.get(url(*path)).mock(return_value=response)
    with pytest.raises(cls) as info:
        get_json(path)
    assert info.value.code == code
    assert info.value.status == response.status_code
    assert str(info.value) == message
    assert isinstance(info.value, gcd.GCDError)


def test_error_details_are_kept(api):
    api.get(url("datasets", "x")).mock(
        return_value=error_response(
            404, "TOPIC_NOT_FOUND", "No dataset 'x'", {"did_you_mean": ["y"]}
        )
    )
    with pytest.raises(gcd.GCDNotFoundError) as info:
        get_json(["datasets", "x"])
    assert info.value.details == {"did_you_mean": ["y"]}


def test_an_error_without_a_message_names_the_status(api):
    api.get(url("x")).mock(return_value=httpx.Response(418, content=b"not json"))
    with pytest.raises(gcd.GCDError) as info:
        get_json("x")
    assert info.value.code == "HTTP_418"
    assert str(info.value) == "I'm a teapot"


def test_a_transport_failure_is_unavailable(api):
    route = api.get(url("datasets")).mock(side_effect=httpx.ConnectError("Could not resolve host"))
    with pytest.raises(gcd.GCDUnavailableError) as info:
        get_json("datasets")
    assert route.call_count == 4
    assert str(info.value) == (
        "Couldn't reach the Georgia Civic Data API.\n"
        "  Check your internet connection, or try again later."
    )
    assert info.value.code == "UNAVAILABLE"
    assert isinstance(info.value.__cause__, httpx.ConnectError)


def test_census_errors_name_the_census_geocoder():
    err = _api.service_error(503, "census")
    assert isinstance(err, gcd.GCDCensusError)
    assert isinstance(err, gcd.GCDUnavailableError)
    assert str(err) == "The U.S. Census geocoder returned an error (HTTP 503).\n  Try again later."
    err = _api.service_error(400, "census")
    assert isinstance(err, gcd.GCDCensusError)
    assert not isinstance(err, gcd.GCDUnavailableError)
    err = _api.unavailable_error(OSError("x"), "census")
    assert str(err).startswith("Couldn't reach the U.S. Census geocoder.")


def test_get_meta_caches_by_url(api):
    route = api.get(url("datasets")).mock(return_value=json_response({"data": []}))
    _cache.get_meta("datasets", {"kind": ["geometry"]})
    _cache.get_meta("datasets", {"kind": ["geometry"]})
    assert route.call_count == 1
    _cache.get_meta("datasets", {"kind": ["table"]})
    assert route.call_count == 2


# Disk cache ------------------------------------------------------------------


def test_the_disk_cache_reuses_a_fresh_response(api):
    route = api.get(url("x")).mock(
        return_value=json_response(
            {"n": 1}, headers={"etag": '"a"', "cache-control": "max-age=300"}
        )
    )
    first = perform("GET", url("x"), cache=True)
    second = perform("GET", url("x"), cache=True)
    assert route.call_count == 1
    assert first.json() == second.json() == {"n": 1}
    assert second.from_cache
    assert any(_cache.cache_dir().iterdir())


def test_the_disk_cache_revalidates_with_the_etag(api, monkeypatch):
    route = api.get(url("x")).mock(
        side_effect=[
            json_response({"n": 1}, headers={"etag": '"a"', "cache-control": "max-age=0"}),
            httpx.Response(304),
            json_response({"n": 2}, headers={"etag": '"b"'}),
        ]
    )
    assert perform("GET", url("x"), cache=True).json() == {"n": 1}
    again = perform("GET", url("x"), cache=True)
    assert again.json() == {"n": 1}
    assert again.from_cache
    assert route.calls[1].request.headers["if-none-match"] == '"a"'
    assert perform("GET", url("x"), cache=True).json() == {"n": 2}


def test_responses_without_validators_are_not_cached(api):
    api.get(url("x")).mock(return_value=json_response({"n": 1}))
    perform("GET", url("x"), cache=True)
    assert not _cache.cache_dir().exists()


def test_the_disk_cache_streams_to_a_file(api, tmp_path):
    api.get(url("x")).mock(
        return_value=httpx.Response(
            200, content=b"a,b\n1,2\n", headers={"etag": '"e"', "cache-control": "max-age=60"}
        )
    )
    first = perform("GET", url("x"), cache=True, stream_to=tmp_path / "one.csv")
    second = perform("GET", url("x"), cache=True, stream_to=tmp_path / "two.csv")
    assert first.bytes == second.bytes == b"a,b\n1,2\n"
    assert second.from_cache
    assert (tmp_path / "two.csv").read_bytes() == b"a,b\n1,2\n"


def test_a_corrupt_cache_entry_is_ignored(api):
    api.get(url("x")).mock(return_value=json_response({"n": 1}, headers={"etag": '"a"'}))
    perform("GET", url("x"), cache=True)
    for f in _cache.cache_dir().glob("*.json"):
        f.write_text("{not json")
    assert perform("GET", url("x"), cache=True).json() == {"n": 1}
