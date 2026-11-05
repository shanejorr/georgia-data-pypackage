from __future__ import annotations

import inspect
import re
from pathlib import Path

import pandas as pd
import pytest

import georgiacivicdata as gcd
from georgiacivicdata._frames import attach
from helpers import seed_grad_schema, seed_meta

PACKAGE_DIR = Path(gcd.__file__).parent
# The source tree (a git checkout or an unpacked sdist), found from this file,
# not from the package: an installed package lives in site-packages.
SOURCE_DIR = Path(__file__).resolve().parents[1]

# Every export of the R package and its Python name.
R_EXPORTS = {
    "gcd_cache_clear": "cache_clear",
    "gcd_citation": "citation",
    "gcd_columns": "columns",
    "gcd_contract": "contract",
    "gcd_datasets": "datasets",
    "gcd_describe": "describe",
    "gcd_dimension": "dimension",
    "gcd_district_boundaries": "district_boundaries",
    "gcd_locate": "locate",
    "gcd_meta": "meta",
    "gcd_rows": "rows",
    "gcd_school_zone_coverage": "school_zone_coverage",
    "gcd_school_zone_status": "school_zone_status",
    "gcd_school_zones": "school_zones",
    "gcd_search": "search",
    "gcd_values": "values",
}


def test_meta_needs_a_result_of_rows():
    with pytest.raises(gcd.GCDError, match="carries no Georgia Civic Data metadata") as info:
        gcd.meta(pd.DataFrame({"a": [1]}))
    assert info.value.code == "NO_METADATA"
    with pytest.raises(gcd.GCDError):
        gcd.meta("not a frame")
    x = attach(pd.DataFrame({"a": [1]}), {"dataset": "d"})
    assert gcd.meta(x) == {"dataset": "d"}


def test_citation_uses_the_apis_citation_or_builds_one():
    with_citation = attach(pd.DataFrame({"a": [1]}), {"citation": "Cite me."})
    assert gcd.citation(with_citation) == "Cite me."
    without = attach(
        pd.DataFrame({"a": [1]}),
        {
            "title": "Unemployment (ACS)",
            "dataset": "employment",
            "source": "U.S. Census Bureau, American Community Survey 5-Year Estimates",
        },
    )
    assert gcd.citation(without) == (
        "Unemployment (ACS). Georgia Civic Data (georgiacivicdata.org), CC BY 4.0. "
        "https://georgiacivicdata.org/api/v1/datasets/employment. Original source: "
        "U.S. Census Bureau, American Community Survey 5-Year Estimates."
    )
    with pytest.raises(TypeError, match=r"result of gcd\.rows"):
        gcd.citation([1])


def test_citation_takes_a_dataset_name():
    seed_grad_schema()
    seed_meta(
        ["datasets", "school_attendance_zones"],
        {
            "name": "school_attendance_zones",
            "kind": "geometry",
            "source": "School district attendance-zone maps.",
        },
    )
    seed_meta(
        "datasets",
        {"data": [{"name": "school_attendance_zones", "title": "School Attendance Zones"}]},
    )
    assert gcd.citation("graduation_rate_4_year_cohort") == (
        "Four-Year Cohort Graduation Rate. Georgia Civic Data (georgiacivicdata.org), CC BY 4.0. "
        "https://georgiacivicdata.org/api/v1/datasets/graduation_rate_4_year_cohort. Original source: "
        "Governor's Office of Education and Workforce Strategy (GOEWS, formerly GOSA)."
    )
    assert gcd.citation("school_attendance_zones") == (
        "School Attendance Zones. Georgia Civic Data (georgiacivicdata.org), CC BY 4.0. "
        "https://georgiacivicdata.org/api/v1/datasets/school_attendance_zones. Original source: "
        "School district attendance-zone maps."
    )
    seed_meta(["datasets", "untitled"], {"name": "untitled"})
    assert gcd.citation("untitled").startswith("untitled. Georgia Civic Data")
    with pytest.raises(gcd.GCDError, match="'counties' is a lookup table; cite the dataset"):
        gcd.citation("counties")


def test_every_r_export_has_a_python_counterpart():
    for r_name, py_name in R_EXPORTS.items():
        assert py_name in gcd.__all__, r_name
        assert callable(getattr(gcd, py_name)), r_name


def test_every_export_is_documented():
    for name in gcd.__all__:
        obj = getattr(gcd, name)
        if name == "__version__":
            continue
        doc = inspect.getdoc(obj) or ""
        assert doc, name
        if inspect.isfunction(obj):
            assert "Returns" in doc, name
            assert "Examples" in doc, name


def test_every_export_is_on_the_reference_page():
    # docs/reference.md lists each export by hand in autosummary blocks; an
    # export missing from it gets no reference page. The sdist has no docs.
    path = SOURCE_DIR / "docs" / "reference.md"
    if not path.exists():
        pytest.skip("docs/reference.md is not in this source tree")
    reference = path.read_text()
    listed: list[str] = []
    for block in re.findall(r"\.\. autosummary::\n(.*?)```", reference, flags=re.DOTALL):
        listed += re.findall(r"^ +([A-Za-z_]\w*)$", block, flags=re.MULTILINE)
    exports = set(gcd.__all__) - {"__version__"}
    assert sorted(exports - set(listed)) == [], "add these to docs/reference.md"
    assert sorted(set(listed) - exports) == [], "remove these from docs/reference.md"
    assert len(listed) == len(set(listed)), "docs/reference.md lists a name twice"


def test_table_functions_take_a_backend_argument():
    for name in (
        "datasets",
        "search",
        "describe",
        "columns",
        "rows",
        "values",
        "dimension",
        "school_zones",
        "district_boundaries",
        "school_zone_status",
        "school_zone_coverage",
        "locate",
    ):
        params = inspect.signature(getattr(gcd, name)).parameters
        assert "backend" in params, name
        assert params["backend"].default is None, name
        assert params["backend"].kind is inspect.Parameter.KEYWORD_ONLY, name


def test_package_source_is_ascii():
    for path in PACKAGE_DIR.glob("*.py"):
        text = path.read_bytes()
        assert all(b < 128 for b in text), f"{path.name} has non-ASCII characters; use \\u escapes"


def test_sub_topic_is_never_mentioned_in_the_public_surface():
    for name in gcd.__all__:
        doc = inspect.getdoc(getattr(gcd, name)) or ""
        assert not re.search(r"\bsub_topic\b", doc), name


def test_version_matches_the_project():
    pyproject = (SOURCE_DIR / "pyproject.toml").read_text()
    match = re.search(r'^version = "([^"]+)"', pyproject, flags=re.MULTILINE)
    assert match
    assert gcd.__version__ == match.group(1)
