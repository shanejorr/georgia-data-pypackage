"""Shared test fixtures (helpers are in ``helpers.py``)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pyarrow as pa
import pytest
import respx

from georgiacivicdata import _api, _cache, _options
from helpers import LOOKUP_TABLES, make_tables, seed_meta


@pytest.fixture
def tables() -> dict[str, pa.Table]:
    """Seed the cached lookup tables the resolver and locate() read."""
    out = make_tables()
    for name, table in out.items():
        _cache.STATE.meta[f"lookup:{name}"] = table
    return out


@pytest.fixture(autouse=True)
def gcd_state(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """A fresh session cache, a temporary disk cache, default options, no
    waiting between retries, and the list of lookup tables seeded so tests
    don't each mock it."""
    saved_meta = dict(_cache.STATE.meta)
    saved_shown = set(_cache.STATE.shown)
    _cache.STATE.meta.clear()
    _cache.STATE.shown.clear()
    _options.reset_options()
    _options.set_option("cache_dir", str(tmp_path / "cache"))
    if not request.node.get_closest_marker("live"):
        monkeypatch.setattr(_api, "_sleep", lambda seconds: None)
        seed_meta("dimensions", {"data": [{"name": n} for n in LOOKUP_TABLES]})
    yield
    _cache.STATE.meta.clear()
    _cache.STATE.meta.update(saved_meta)
    _cache.STATE.shown.clear()
    _cache.STATE.shown.update(saved_shown)
    _options.reset_options()


@pytest.fixture(autouse=True)
def api(request: pytest.FixtureRequest) -> Iterator[respx.MockRouter | None]:
    """Every request is mocked; an unmatched request fails the test. Live
    tests (marked ``live``) reach the network instead."""
    if request.node.get_closest_marker("live"):
        yield None
        return
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router
