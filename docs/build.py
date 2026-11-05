"""Build the documentation site: HTML, a Markdown twin of every page, and
llms.txt.

    uv run python docs/build.py            # writes docs/_build/html
    uv run python docs/build.py --strict   # warnings are errors (CI)

Steps:

1. Sphinx builds the HTML site into ``docs/_build/html``.
2. Sphinx builds the same sources as Markdown (sphinx-markdown-builder)
   into ``docs/_build/markdown``.
3. Each Markdown page is copied beside its HTML page (``articles/analysis.html``
   and ``articles/analysis.md``), so an agent can add ``.md`` to any address.
   Every HTML page links to its twin with ``<link rel="alternate"
   type="text/markdown">`` (see ``conf.py``).
4. ``llms.txt`` (an index of the Markdown pages, per https://llmstxt.org) and
   ``llms-full.txt`` (every page in one file) are written at the site root.
5. ``.nojekyll`` is written so GitHub Pages serves the ``_static`` folders.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
BUILD = DOCS / "_build"
HTML = BUILD / "html"
MARKDOWN = BUILD / "markdown"
SITE_URL = "https://georgiacivicdata.org/py/"

# The pages llms.txt lists first, in order, with a one-line description.
GUIDES = [
    ("index", "Home", "what the package does, installation and a first walkthrough"),
    (
        "articles/get-started",
        "Get started",
        "the catalog, names and filters, and the rules of the data",
    ),
    (
        "articles/analysis",
        "Analyzing Georgia data",
        "joining two datasets and pooling rates from counts",
    ),
    (
        "articles/school-zones",
        "School zones and places",
        "maps, zone status and locating points and addresses",
    ),
    (
        "coming-from-r",
        "Coming from R",
        "the R and Python functions side by side, and how they differ",
    ),
    ("agents", "For LLM agents", "the Markdown pages and llms.txt"),
    ("reference", "Reference", "every function, grouped by task"),
    ("articles/index", "Articles", "the list of worked examples"),
    ("news", "Changelog", "what changed in each version"),
]


def sphinx(builder: str, out: Path, strict: bool) -> None:
    cmd = [sys.executable, "-m", "sphinx", "-b", builder, "-q", "-j", "auto", str(DOCS), str(out)]
    if strict:
        cmd[3:3] = ["-W", "--keep-going"]
    print("+", " ".join(cmd[2:]))
    subprocess.run(cmd, check=True)


def title_of(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def clean_markdown(text: str) -> str:
    """Tidy the builder's output: Python and text code fences, no runs of
    blank lines."""
    text = re.sub(r"^```ipython3$", "```python", text, flags=re.MULTILINE)
    text = re.sub(r"^```myst-ansi$", "```text", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def fix_images(text: str, rel: Path) -> str:
    """Point notebook figures at the copies the HTML build keeps in
    ``_images/`` (the Markdown builder links the execution folder)."""
    prefix = "../" * (len(rel.parts) - 1) + "_images/"

    def repl(match: re.Match[str]) -> str:
        name = match.group(2)
        if not (HTML / "_images" / name).exists():
            raise FileNotFoundError(f"{rel}: figure {name} is not in the HTML build")
        return f"]({prefix}{name})"

    return re.sub(
        r"\]\((?:\.\./)*(_build/jupyter_execute|_images)/([^)/]+\.(?:png|svg|jpg))\)", repl, text
    )


def first_paragraph(md: str) -> str:
    """The first paragraph of prose after the headings (one line)."""
    lines: list[str] = []
    for line in md.splitlines()[1:]:
        if line.startswith("#") or not line.strip():
            if lines:
                break
            continue
        lines.append(line.strip())
    return " ".join(lines)


def copy_twins() -> list[Path]:
    """Copy every Markdown page beside its HTML page; return their paths."""
    pages = []
    for md in sorted(MARKDOWN.rglob("*.md")):
        rel = md.relative_to(MARKDOWN)
        if not (HTML / rel.with_suffix(".html")).exists():
            continue
        target = HTML / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = clean_markdown(md.read_text(encoding="utf-8"))
        target.write_text(fix_images(text, rel), encoding="utf-8")
        pages.append(rel)
    return pages


def write_llms(pages: list[Path]) -> None:
    by_name = {p.with_suffix("").as_posix(): p for p in pages}
    lines = [
        "# georgiacivicdata",
        "",
        "> The Python client for the Georgia Civic Data REST API "
        "(https://georgiacivicdata.org/api/v1): cleaned public data about Georgia "
        "(education, Census, health, immigration) as pandas or Polars data frames, "
        "school attendance zones as geopandas GeoDataFrames, and point and address "
        "lookups. No API key. `import georgiacivicdata as gcd`.",
        "",
        "Every page of this site has a Markdown twin: add `.md` to its address "
        "(`.../articles/analysis.html` -> `.../articles/analysis.md`). "
        "`llms-full.txt` holds every page in one file. The R package with the same "
        "functions is documented at https://georgiacivicdata.org/r/.",
        "",
        "## Guides",
        "",
    ]
    listed = set()
    for name, title, description in GUIDES:
        if name in by_name:
            lines.append(f"- [{title}]({SITE_URL}{name}.md): {description}")
            listed.add(name)
    reference = sorted(n for n in by_name if n.startswith("generated/"))
    lines += ["", "## Functions", ""]
    for name in reference:
        md = (HTML / by_name[name]).read_text(encoding="utf-8")
        title = name.split(".")[-1]
        summary = first_paragraph(md)
        lines.append(f"- [{title}]({SITE_URL}{name}.md): {summary}")
        listed.add(name)
    others = sorted(n for n in by_name if n not in listed)
    if others:
        lines += ["", "## Optional", ""]
        lines += [f"- [{n}]({SITE_URL}{n}.md)" for n in others]
    (HTML / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    order = [n for n, _, _ in GUIDES if n in by_name] + reference + others
    parts = []
    for name in order:
        text = (HTML / by_name[name]).read_text(encoding="utf-8")
        parts.append(f"<!-- {SITE_URL}{name}.md -->\n\n{text}")
    (HTML / "llms-full.txt").write_text("\n\n---\n\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="turn Sphinx warnings into errors")
    args = parser.parse_args()
    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(DOCS / "generated", ignore_errors=True)
    sphinx("html", HTML, args.strict)
    sphinx("markdown", MARKDOWN, args.strict)
    pages = copy_twins()
    write_llms(pages)
    (HTML / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Built {len(pages)} pages with Markdown twins in {HTML}")


if __name__ == "__main__":
    main()
