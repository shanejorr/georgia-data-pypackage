"""Sphinx configuration for the georgiacivicdata documentation.

Build with ``uv run python docs/build.py`` (HTML, Markdown twins and
llms.txt). The articles in ``articles/`` are notebooks executed ahead of
time by ``docs/precompile.py``; Sphinx never executes them.
"""

from __future__ import annotations

import posixpath
from typing import Any

import georgiacivicdata

project = "georgiacivicdata"
author = "Shane Orr"
copyright = "2026, Shane Orr. Data: Georgia Civic Data (georgiacivicdata.org), CC BY 4.0"
release = georgiacivicdata.__version__
version = release

SITE_URL = "https://georgiacivicdata.org/py/"

extensions = [
    "myst_nb",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
    "sphinx_markdown_builder",
]

exclude_patterns = [
    "_build",
    "notebooks",
    "jupyter_execute",
    "**.ipynb_checkpoints",
    "Thumbs.db",
    ".DS_Store",
]
templates_path = ["_templates"]
smartquotes = False  # keep quotes as written (plain ASCII in the Markdown twins)

# MyST and notebooks -----------------------------------------------------------

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3
nb_execution_mode = "off"
nb_merge_streams = True
# Markdown pages show plain-text tables, not HTML ones.
# (Lower numbers win: figures as images, tables as text.)
nb_mime_priority_overrides = [
    ("markdown", "image/png", 0),
    ("markdown", "text/plain", 10),
    ("markdown", "text/html", None),
]

# API reference ----------------------------------------------------------------

autosummary_generate = True
autodoc_typehints = "none"
autodoc_member_order = "bysource"
autodoc_default_options = {"members": False}
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_rtype = False
napoleon_use_ivar = True

# HTML -------------------------------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_title = "georgiacivicdata"
html_baseurl = SITE_URL
html_favicon = "_static/favicon.ico"
html_static_path = ["_static"]
html_css_files = [
    "https://fonts.googleapis.com/css2?family=Figtree:wght@500;700"
    "&family=Inter:wght@400;600&family=JetBrains+Mono&display=swap",
    "custom.css",
]
html_copy_source = False
html_show_sourcelink = False
html_theme_options = {
    "logo": {"text": "georgiacivicdata"},
    "github_url": "https://github.com/shanejorr/georgia-data-pypackage",
    "external_links": [
        {"name": "Georgia Civic Data", "url": "https://georgiacivicdata.org"},
    ],
    "header_links_before_dropdown": 6,
    "navbar_align": "left",
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "secondary_sidebar_items": ["page-toc", "markdown-link"],
    "footer_start": ["copyright"],
    "footer_end": ["data-license"],
    "show_prev_next": False,
    "navigation_with_keys": False,
}
html_sidebars = {"index": [], "news": [], "reference": []}

# Markdown builder ------------------------------------------------------------

markdown_http_base = SITE_URL.rstrip("/")
markdown_uri_doc_suffix = ".md"


def _markdown_twin(
    app: Any, pagename: str, templatename: str, context: dict[str, Any], doctree: Any
) -> None:
    """Point every HTML page at its Markdown twin (``foo.html`` -> ``foo.md``)."""
    if app.builder.name != "html" or doctree is None:
        return
    twin = posixpath.basename(pagename) + ".md"
    context["markdown_url"] = twin
    link = f'<link rel="alternate" type="text/markdown" href="{twin}" title="Markdown">'
    context["metatags"] = context.get("metatags", "") + "\n" + link


def _pass(self: Any, node: Any) -> None:
    """Render a node's children as they are (the Markdown builder skips
    node types it doesn't know, such as the ``*`` in signatures)."""


def setup(app: Any) -> dict[str, Any]:
    from docutils import nodes

    app.add_node(nodes.abbreviation, override=True, markdown=(_pass, _pass))
    app.connect("html-page-context", _markdown_twin)
    return {"parallel_read_safe": True}
