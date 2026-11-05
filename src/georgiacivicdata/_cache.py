"""Session cache (metadata) and the opt-in disk cache (rows)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import platformdirs

from . import _options

if TYPE_CHECKING:
    import httpx

T = TypeVar("T")


@dataclass
class _State:
    """Package-level state: cached metadata, once-per-session flags and the
    shared HTTP client."""

    meta: dict[str, Any] = field(default_factory=dict)
    shown: set[str] = field(default_factory=set)
    client: httpx.Client | None = None


STATE = _State()


def cache_get_or_set(key: str, compute: Callable[[], T]) -> T:
    """Get a cached metadata value, or compute and store it."""
    if key in STATE.meta:
        return STATE.meta[key]  # type: ignore[no-any-return]
    value = compute()
    STATE.meta[key] = value
    return value


def get_meta(path: str | list[str], query: dict[str, list[str]] | None = None) -> Any:
    """GET a JSON metadata resource, cached for the session by URL.

    The cached value is shared: callers must not modify it.
    """
    from ._api import build_url, perform

    url = build_url(path, query)
    return cache_get_or_set("json:" + url, lambda: perform("GET", url).json())


def first_time(key: str) -> bool:
    """Has this once-per-session message not been shown yet? Marks it shown."""
    if key in STATE.shown:
        return False
    STATE.shown.add(key)
    return True


def cache_dir() -> Path:
    """The disk cache directory for row responses."""
    configured = _options.get_option("cache_dir")
    if configured is not None:
        return Path(configured)
    return Path(platformdirs.user_cache_dir("georgiacivicdata", appauthor=False))


def cache_clear() -> None:
    """Clear the session cache and the disk cache.

    Empties the in-memory cache of metadata (the catalog, dataset schemas and
    lookup tables) kept for the Python session, and deletes the opt-in disk
    cache of row downloads (see the ``cache`` argument of :func:`rows`).
    Location lookups are never cached, so there is nothing to clear for them.

    The disk cache lives in the standard user cache folder for
    ``georgiacivicdata`` (or the ``cache_dir`` option). It is only ever
    written when you ask for it, with ``cache=True`` or
    ``set_option("cache", True)``.

    Returns
    -------
    None

    See Also
    --------
    rows : the disk cache.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.cache_clear()
    """
    STATE.meta.clear()
    STATE.shown.clear()
    folder = cache_dir()
    if folder.exists():
        shutil.rmtree(folder)
