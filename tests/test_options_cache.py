from __future__ import annotations

from pathlib import Path

import platformdirs
import pytest

import georgiacivicdata as gcd
from georgiacivicdata import _cache, _options


def test_options_have_defaults():
    _options.reset_options()
    assert gcd.get_option("backend") == "pandas"
    assert gcd.get_option("quiet") is False
    assert gcd.get_option("cache") is False
    assert gcd.get_option("cache_dir") is None


def test_set_option_validates():
    gcd.set_option("backend", "polars")
    assert gcd.get_option("backend") == "polars"
    with pytest.raises(ValueError, match="'pandas' or 'polars'"):
        gcd.set_option("backend", "arrow")
    with pytest.raises(TypeError, match="True or False"):
        gcd.set_option("quiet", "yes")
    with pytest.raises(TypeError, match="a path or None"):
        gcd.set_option("cache_dir", 1)
    with pytest.raises(KeyError, match="Unknown option 'nope'"):
        gcd.set_option("nope", 1)
    with pytest.raises(KeyError):
        gcd.get_option("nope")


def test_option_context_restores_values():
    with gcd.option_context(backend="polars", quiet=True):
        assert gcd.get_option("backend") == "polars"
        assert gcd.get_option("quiet") is True
    assert gcd.get_option("backend") == "pandas"
    assert gcd.get_option("quiet") is False
    with pytest.raises(ValueError, match="'pandas' or 'polars'"), gcd.option_context(backend="x"):
        pass


def test_resolve_backend_and_is_quiet():
    assert _options.resolve_backend(None) == "pandas"
    assert _options.resolve_backend("polars") == "polars"
    with pytest.raises(ValueError, match="`backend`"):
        _options.resolve_backend("arrow")
    assert _options.is_quiet() is False
    assert _options.is_quiet(True) is True
    with gcd.option_context(quiet=True):
        assert _options.is_quiet() is True


def test_cache_get_or_set_computes_once():
    calls = []

    def compute():
        calls.append(1)
        return "value"

    assert _cache.cache_get_or_set("k", compute) == "value"
    assert _cache.cache_get_or_set("k", compute) == "value"
    assert len(calls) == 1


def test_first_time_is_true_once_per_key():
    assert _cache.first_time("note") is True
    assert _cache.first_time("note") is False


def test_cache_dir_defaults_to_the_user_cache_folder():
    gcd.set_option("cache_dir", None)
    expected = Path(platformdirs.user_cache_dir("georgiacivicdata", appauthor=False))
    assert _cache.cache_dir() == expected


def test_cache_clear_empties_the_session_and_disk_caches():
    _cache.cache_get_or_set("k", lambda: 1)
    _cache.first_time("note")
    folder = _cache.cache_dir()
    folder.mkdir(parents=True)
    (folder / "file").write_text("x")
    assert gcd.cache_clear() is None
    assert _cache.STATE.meta == {}
    assert _cache.STATE.shown == set()
    assert not folder.exists()
    assert gcd.cache_clear() is None
