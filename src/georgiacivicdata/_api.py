"""The HTTP layer: URL building, one performer with retries and the opt-in
ETag disk cache, and the error-envelope parser that turns API errors into
exceptions."""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from . import _cache
from ._errors import (
    GCDCensusError,
    GCDError,
    GCDNotFoundError,
    GCDUnavailableError,
    _CensusUnavailableError,
    format_message,
    quote_list,
)
from ._messages import inform
from ._version import __version__

BASE_URL = "https://georgiacivicdata.org/api/v1"
"""The API's base URL (no option to change it, by design)."""

TRANSIENT_STATUSES = frozenset({429, 502, 503, 504})
"""Statuses retried automatically (rate limits and gateway hiccups)."""

REPO_URL = "https://github.com/shanejorr/georgia-data-pypackage"

Query = Mapping[str, Sequence[str]]


def user_agent() -> str:
    """The package's user agent."""
    return f"georgiacivicdata-py/{__version__} (+{REPO_URL})"


def path_segment(x: str) -> str:
    """Escape one path segment (a dataset or table name)."""
    return quote(x, safe="")


def build_url(path: str | Sequence[str], query: Query | None = None, base: str = BASE_URL) -> str:
    """A URL below the base: path segments are escaped; list values are
    escaped one by one and joined with literal commas."""
    if isinstance(path, str):
        path = [path]
    url = base.rstrip("/") + "/" + "/".join(path_segment(p) for p in path)
    pairs = []
    for name, values in (query or {}).items():
        joined = ",".join(quote(str(v), safe="") for v in values)
        pairs.append(f"{quote(name, safe='')}={joined}")
    if pairs:
        url += "?" + "&".join(pairs)
    return url


def _client() -> httpx.Client:
    """The shared client (connection pooling across a session)."""
    if _cache.STATE.client is None:
        _cache.STATE.client = httpx.Client(
            headers={"User-Agent": user_agent()},
            follow_redirects=True,
        )
    return _cache.STATE.client


# Responses -------------------------------------------------------------------


@dataclass
class Response:
    """What a request returned: status, headers and the body (in memory, or
    in ``path`` when it was streamed to a file)."""

    status: int
    headers: dict[str, str]
    content: bytes = b""
    path: Path | None = None
    url: str = ""
    from_cache: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        if self.path is not None:
            return self.path.read_text(encoding="utf-8")
        return self.content.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.text)

    @property
    def bytes(self) -> bytes:
        if self.path is not None:
            return self.path.read_bytes()
        return self.content


def _headers(resp: httpx.Response) -> dict[str, str]:
    return {k.lower(): v for k, v in resp.headers.items()}


# Retries ---------------------------------------------------------------------


def _sleep(seconds: float) -> None:
    """Wait between retries (tests replace it)."""
    time.sleep(seconds)


def retry_after(headers: Mapping[str, str]) -> float | None:
    """Seconds to wait from a ``Retry-After`` header (seconds or a date)."""
    value = headers.get("retry-after")
    if value is None:
        return None
    value = value.strip()
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def _backoff(tries: int) -> float:
    return round(min(random.uniform(1, 2**tries), 60.0), 1)


def _retry_note(status: int, wait: float | None) -> str:
    what = (
        "The API's rate limit was reached"
        if status == 429
        else f"The server is busy (HTTP {status})"
    )
    if wait is None:
        return f"{what}; retrying shortly."
    seconds = int(wait) if float(wait).is_integer() else wait
    unit = "second" if seconds == 1 else "seconds"
    return f"{what}; retrying in {seconds} {unit}."


# Disk cache ------------------------------------------------------------------


def _cache_paths(url: str) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    folder = _cache.cache_dir()
    return folder / f"{key}.body", folder / f"{key}.json"


def _max_age(cache_control: str | None) -> float | None:
    if not cache_control:
        return None
    match = re.search(r"(?:^|,)\s*max-age\s*=\s*(\d+)", cache_control)
    return float(match.group(1)) if match else None


def _cache_read(url: str) -> tuple[Path, dict[str, Any]] | None:
    body, meta = _cache_paths(url)
    if not (body.exists() and meta.exists()):
        return None
    try:
        info = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return body, info


def _cache_write(url: str, resp: httpx.Response, body_path: Path | None, content: bytes) -> None:
    headers = _headers(resp)
    if "etag" not in headers and _max_age(headers.get("cache-control")) is None:
        return
    body, meta = _cache_paths(url)
    body.parent.mkdir(parents=True, exist_ok=True)
    if body_path is not None:
        shutil.copyfile(body_path, body)
    else:
        body.write_bytes(content)
    info = {
        "url": url,
        "status": resp.status_code,
        "etag": headers.get("etag"),
        "cache_control": headers.get("cache-control"),
        "content_type": headers.get("content-type"),
        "x_total_count": headers.get("x-total-count"),
        "stored_at": time.time(),
    }
    meta.write_text(json.dumps(info), encoding="utf-8")


def _cache_touch(url: str, info: dict[str, Any], resp: httpx.Response) -> None:
    """A 304 confirms the copy: restart its freshness clock."""
    headers = _headers(resp)
    info["stored_at"] = time.time()
    if headers.get("cache-control"):
        info["cache_control"] = headers["cache-control"]
    _, meta = _cache_paths(url)
    meta.write_text(json.dumps(info), encoding="utf-8")


def _cached_response(
    body: Path, info: dict[str, Any], url: str, stream_to: Path | None
) -> Response:
    headers = {
        k.replace("_", "-"): v
        for k, v in (
            ("content-type", info.get("content_type")),
            ("etag", info.get("etag")),
            ("x-total-count", info.get("x_total_count")),
        )
        if v is not None
    }
    if stream_to is not None:
        shutil.copyfile(body, stream_to)
        return Response(200, headers, path=stream_to, url=url, from_cache=True)
    return Response(200, headers, content=body.read_bytes(), url=url, from_cache=True)


# Performing ------------------------------------------------------------------


def perform(
    method: str,
    url: str,
    *,
    json_body: Any = None,
    files: Any = None,
    data: Mapping[str, str] | None = None,
    timeout: float = 60,
    cache: bool = False,
    service: str = "api",
    max_tries: int = 4,
    max_seconds: float = 180,
    stream_to: Path | None = None,
) -> Response:
    """Send a request with retries, raising a :class:`GCDError` on failure.

    ``cache`` (GET only) keeps the response with its ``ETag`` in the disk
    cache: a fresh copy is reused without asking; a stale one is
    revalidated with ``If-None-Match`` and reused on ``304``.
    """
    cached = _cache_read(url) if cache and method == "GET" else None
    headers: dict[str, str] = {}
    if cached is not None:
        body, info = cached
        age = time.time() - float(info.get("stored_at", 0))
        max_age = _max_age(info.get("cache_control"))
        if max_age is not None and age < max_age:
            return _cached_response(body, info, url, stream_to)
        if info.get("etag"):
            headers["If-None-Match"] = str(info["etag"])

    client = _client()
    started = time.monotonic()
    tries = 0
    while True:
        tries += 1
        try:
            request = client.build_request(
                method,
                url,
                json=json_body,
                files=files,
                data=data,
                headers=headers,
                timeout=timeout,
            )
            resp = client.send(request, stream=True)
            try:
                if stream_to is not None and resp.status_code < 300:
                    with stream_to.open("wb") as fh:
                        for chunk in resp.iter_bytes():
                            fh.write(chunk)
                    content = b""
                else:
                    content = resp.read()
            finally:
                resp.close()
        except httpx.TransportError as exc:
            elapsed = time.monotonic() - started
            if tries < max_tries and elapsed < max_seconds:
                _sleep(_backoff(tries))
                continue
            raise unavailable_error(exc, service) from exc
        status = resp.status_code
        if status in TRANSIENT_STATUSES and tries < max_tries:
            wait = retry_after(_headers(resp))
            delay = wait if wait is not None else _backoff(tries)
            if time.monotonic() - started + delay <= max_seconds:
                inform(_retry_note(status, wait))
                _sleep(delay)
                continue
        break

    if status == 304 and cached is not None:
        body, info = cached
        _cache_touch(url, info, resp)
        return _cached_response(body, info, url, stream_to)
    if status >= 400:
        if service == "api":
            raise api_error(status, _headers(resp), content)
        raise service_error(status, service)
    if cache and method == "GET":
        _cache_write(url, resp, stream_to, content)
    if stream_to is not None:
        return Response(status, _headers(resp), path=stream_to, url=url)
    return Response(status, _headers(resp), content=content, url=url)


def get_json(path: str | Sequence[str], query: Query | None = None, timeout: float = 60) -> Any:
    """GET a JSON resource from the API."""
    return perform("GET", build_url(path, query), timeout=timeout).json()


# Errors ----------------------------------------------------------------------


def _service_label(service: str) -> str:
    return "the U.S. Census geocoder" if service == "census" else "the Georgia Civic Data API"


def api_error(status: int, headers: Mapping[str, str], content: bytes) -> GCDError:
    """Turn an API error response into a :class:`GCDError`."""
    envelope: Any = None
    try:
        envelope = json.loads(content.decode("utf-8")).get("error")
    except (ValueError, AttributeError, UnicodeDecodeError):
        envelope = None
    if not isinstance(envelope, dict):
        envelope = {}
    code = str(envelope.get("code") or f"HTTP_{status}")
    api_message = str(envelope.get("message") or httpx.codes.get_reason_phrase(status) or "")
    if not api_message:
        api_message = "The request failed."
    details = envelope.get("details")
    if not isinstance(details, dict):
        details = {}

    lead = api_message
    bullets: list[str] = []
    if status >= 500:
        lead = f"The Georgia Civic Data API couldn't answer (HTTP {status})."
        bullets = [api_message, "Try again in a few minutes."]
    if status == 429:
        wait = retry_after(headers)
        lead = "The Georgia Civic Data API's rate limit was reached."
        if wait is None:
            bullets = ["Try again shortly."]
        else:
            seconds = int(wait) if float(wait).is_integer() else wait
            bullets = [f"Try again in {seconds} second{'' if seconds == 1 else 's'}."]
    dym = _as_list(details.get("did_you_mean"))
    if dym:
        bullets.append(f"Did you mean: {quote_list(dym)}?")
    hint = details.get("hint")
    if isinstance(hint, str):
        bullets.append(hint)
    moved = details.get("moved_to")
    if isinstance(moved, str):
        bullets.append(f"Moved to {moved}.")
    available = _as_list(details.get("available"))
    if available:
        bullets.append(f"Available: {quote_list(available)}.")
    valid = _as_list(details.get("valid"))
    if valid:
        bullets.append(f"Valid values: {quote_list(valid)}.")

    cls: type[GCDError] = GCDError
    if status >= 500 or status == 429:
        cls = GCDUnavailableError
    elif status == 404:
        cls = GCDNotFoundError
    return cls(format_message(lead, bullets), code=code, status=status, details=details)


def _as_list(x: Any) -> list[Any]:
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return list(x)
    return [x]


def unavailable_error(exc: BaseException, service: str = "api") -> GCDError:
    """The API (or the Census geocoder) could not be reached at all."""
    what = _service_label(service)
    message = format_message(
        f"Couldn't reach {what}.",
        ["Check your internet connection, or try again later."],
    )
    cls: type[GCDError] = _CensusUnavailableError if service == "census" else GCDUnavailableError
    return cls(message, code="UNAVAILABLE", status=None, details={})


def service_error(status: int, service: str = "census") -> GCDError:
    """An HTTP error from a service other than the API (the Census geocoder)."""
    what = _service_label(service)
    what = what[0].upper() + what[1:]
    message = format_message(f"{what} returned an error (HTTP {status}).", ["Try again later."])
    cls: type[GCDError] = (
        _CensusUnavailableError if status >= 500 or status == 429 else GCDCensusError
    )
    return cls(message, code=f"HTTP_{status}", status=status, details={})
