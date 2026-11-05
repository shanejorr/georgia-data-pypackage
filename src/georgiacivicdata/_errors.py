"""Exceptions raised by the package.

API errors keep the API's own ``code`` (``TOPIC_NOT_FOUND``,
``INVALID_FILTER_VALUE``, ...), the HTTP ``status`` and the error's
``details``, so scripts can catch one failure precisely.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

__all__ = [
    "GCDCensusError",
    "GCDError",
    "GCDNotFoundError",
    "GCDPlaceAmbiguousError",
    "GCDPlaceNotFoundError",
    "GCDUnavailableError",
]


class GCDError(Exception):
    """Base class of every error from the Georgia Civic Data API or this package.

    Attributes
    ----------
    message : str
        The full message.
    code : str
        The API's error code (``"TOPIC_NOT_FOUND"``, ``"UNSUPPORTED_FILTER"``,
        ...) or the package's own (``"PLACE_NOT_FOUND"``, ``"NOT_A_DATASET"``,
        ...). Without an envelope, ``"HTTP_<status>"``.
    status : int or None
        The HTTP status, or ``None`` when no HTTP response was involved.
    details : dict
        The error's details, such as ``did_you_mean`` suggestions.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.details = details if details is not None else {}


class GCDUnavailableError(GCDError):
    """The service couldn't answer: no connection, a timeout, a rate limit
    that outlasted the retries, or a server error (HTTP 5xx)."""


class GCDNotFoundError(GCDError):
    """No such dataset, lookup table or path (HTTP 404)."""


class GCDPlaceNotFoundError(GCDError):
    """A district, school or county name matched nothing."""


class GCDPlaceAmbiguousError(GCDError):
    """A district, school or county name matched more than one place."""


class GCDCensusError(GCDError):
    """The U.S. Census geocoder returned an error."""


class _CensusUnavailableError(GCDCensusError, GCDUnavailableError):
    """The U.S. Census geocoder couldn't answer."""


def format_message(lead: str, bullets: Iterable[str] = ()) -> str:
    """A message: one lead line, then indented bullet lines."""
    lines = [lead]
    lines.extend(f"  {b}" for b in bullets if b)
    return "\n".join(lines)


def quote_list(values: Iterable[Any]) -> str:
    """'a', 'b' and 'c' -> "'a', 'b', 'c'"."""
    return ", ".join(repr(str(v)) for v in values)


def gcd_error(
    lead: str,
    bullets: Iterable[str] = (),
    *,
    code: str,
    details: dict[str, Any] | None = None,
    cls: type[GCDError] = GCDError,
) -> GCDError:
    """A package-side error (no HTTP involved)."""
    return cls(format_message(lead, bullets), code=code.upper(), status=None, details=details)
