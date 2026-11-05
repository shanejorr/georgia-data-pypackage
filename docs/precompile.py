"""Precompute the articles.

They call the live Georgia Civic Data API, which CI builds must not, so each
``docs/notebooks/<name>.md`` (a jupytext MyST notebook) is executed here,
locally, and saved with its outputs and figures as an ``.ipynb``:
``index.md`` becomes ``docs/index.ipynb``, every other source
``docs/articles/<name>.ipynb``. Commit the results. Run from the repo root:

    uv run python docs/precompile.py             # every article
    uv run python docs/precompile.py analysis    # one article

This mirrors the R package's precomputed vignettes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import jupytext
import nbformat
from nbclient import NotebookClient

DOCS = Path(__file__).resolve().parent
SOURCES = DOCS / "notebooks"


def target(src: Path) -> Path:
    if src.stem == "index":
        return DOCS / "index.ipynb"
    return DOCS / "articles" / f"{src.stem}.ipynb"


def run(src: Path) -> None:
    out = target(src)
    print(f"Executing {src.relative_to(DOCS)} -> {out.relative_to(DOCS)}")
    nb = jupytext.read(src)
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.metadata.pop("jupytext", None)
    client = NotebookClient(
        nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(DOCS)}}
    )
    client.execute()
    for cell in nb.cells:
        cell.metadata.pop("execution", None)
    out.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, out)


def main(names: list[str]) -> None:
    sources = sorted(SOURCES.glob("*.md"))
    if names:
        sources = [s for s in sources if s.stem in names]
        if not sources:
            sys.exit(f"No article named {', '.join(names)} in {SOURCES}")
    for src in sources:
        run(src)


if __name__ == "__main__":
    main(sys.argv[1:])
