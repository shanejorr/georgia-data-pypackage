"""Package options: the dataframe backend, quiet mode and the disk cache."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

__all__ = ["get_option", "option_context", "set_option"]

_DEFAULTS: dict[str, Any] = {
    "backend": "pandas",
    "quiet": False,
    "cache": False,
    "cache_dir": None,
}

_options: dict[str, Any] = dict(_DEFAULTS)

BACKENDS = ("pandas", "polars")


def _check(name: str, value: Any) -> Any:
    if name not in _DEFAULTS:
        known = ", ".join(repr(k) for k in _DEFAULTS)
        raise KeyError(f"Unknown option {name!r}. Options are {known}.")
    if name == "backend":
        if value not in BACKENDS:
            raise ValueError("Option 'backend' must be 'pandas' or 'polars'.")
    elif name in ("quiet", "cache"):
        if not isinstance(value, bool):
            raise TypeError(f"Option {name!r} must be True or False.")
    elif name == "cache_dir" and value is not None and not isinstance(value, (str, os.PathLike)):
        raise TypeError("Option 'cache_dir' must be a path or None.")
    return value


def get_option(name: str) -> Any:
    """Get the value of a package option.

    Parameters
    ----------
    name : str
        One of ``"backend"``, ``"quiet"``, ``"cache"`` or ``"cache_dir"``
        (see :func:`set_option`).

    Returns
    -------
    Any
        The option's current value.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.get_option("backend")
    'pandas'
    """
    if name not in _DEFAULTS:
        _check(name, None)
    return _options[name]


def set_option(name: str, value: Any) -> None:
    """Set a package option for the rest of the session.

    Parameters
    ----------
    name : str
        The option:

        - ``"backend"``: ``"pandas"`` (default) or ``"polars"``, the kind of
          data frame every table function returns when its ``backend``
          argument is not given.
        - ``"quiet"``: ``True`` silences the advisories of :func:`rows` and
          the notes of the search and zone functions. Default ``False``.
        - ``"cache"``: ``True`` turns on the disk cache of :func:`rows` (see
          that function). Default ``False``.
        - ``"cache_dir"``: where the disk cache lives. Default ``None``: the
          standard user cache folder for ``georgiacivicdata``.
    value : Any
        The new value.

    Returns
    -------
    None

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> gcd.set_option("backend", "polars")
    >>> gcd.set_option("backend", "pandas")
    """
    _options[name] = _check(name, value)


@contextmanager
def option_context(**options: Any) -> Iterator[None]:
    """Set options temporarily, inside a ``with`` block.

    Parameters
    ----------
    **options : Any
        Options and their values, as in :func:`set_option`.

    Returns
    -------
    contextmanager
        A context manager that restores the previous values on exit.

    Examples
    --------
    >>> import georgiacivicdata as gcd
    >>> with gcd.option_context(backend="polars", quiet=True):
    ...     gcd.get_option("backend")
    'polars'
    """
    for name, value in options.items():
        _check(name, value)
    saved = {name: _options[name] for name in options}
    _options.update(options)
    try:
        yield
    finally:
        _options.update(saved)


def reset_options() -> None:
    """Restore every option to its default (used by the tests)."""
    _options.clear()
    _options.update(_DEFAULTS)


def is_quiet(quiet: bool = False) -> bool:
    """Is the advisory and note output silenced?"""
    return bool(quiet) or bool(_options["quiet"])


def resolve_backend(backend: str | None) -> str:
    """The backend for one call: the argument, else the option."""
    if backend is None:
        return str(_options["backend"])
    if backend not in BACKENDS:
        raise ValueError("`backend` must be 'pandas' or 'polars'.")
    return backend
