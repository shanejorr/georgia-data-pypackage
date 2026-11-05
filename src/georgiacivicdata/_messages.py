"""User-facing messages.

Two channels, both silenced by ``quiet=True`` or ``set_option("quiet", True)``:

- **Advisories** (the API's advisories on a result, search notes, the
  zones' assignment note) are :class:`GCDAdvisory` warnings, the Python
  idiom for "this result needs care": they can be filtered, recorded or
  turned into errors with the :mod:`warnings` machinery. The package shows
  every one (a ``warnings`` filter set at import), once per call.
- **Notes** on progress (a large download, a rate-limit wait) go to
  standard error, like R's ``message()``.
"""

from __future__ import annotations

import os
import sys
import warnings
from types import FrameType

from ._options import is_quiet

__all__ = ["GCDAdvisory"]


class GCDAdvisory(UserWarning):
    """An advisory about a result: suppressed values, totals that must not be
    added to their subgroups, a search with no good match, and so on."""


# Show every advisory, not only the first per call site.
warnings.filterwarnings("always", category=GCDAdvisory)


_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def _caller_stacklevel() -> int:
    """The ``stacklevel`` of the first frame outside this package, so a
    warning points at the user's own line of code."""
    level = 1
    frame: FrameType | None = sys._getframe(1)
    while frame is not None:
        filename = os.path.abspath(frame.f_code.co_filename)
        if not filename.startswith(_PACKAGE_DIR):
            return level
        frame = frame.f_back
        level += 1
    return level


def advise(message: str, *, quiet: bool = False) -> None:
    """Emit one advisory unless output is silenced."""
    if is_quiet(quiet):
        return
    warnings.warn(message, GCDAdvisory, stacklevel=_caller_stacklevel())


def inform(message: str, *, quiet: bool = False) -> None:
    """Print a progress note to standard error unless output is silenced."""
    if is_quiet(quiet):
        return
    print(f"i {message}", file=sys.stderr)
