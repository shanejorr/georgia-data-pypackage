`AGENTS.md` is a symlink to this file; edit `CLAUDE.md` only.

# georgiacivicdata (Python): agent instructions

## What this is

`georgiacivicdata` is the Python client for the Georgia Civic Data REST
API, `https://georgiacivicdata.org/api/v1` (production, read-only, no
key). It returns pandas (default) or Polars data frames typed from each
dataset's schema, geopandas `GeoDataFrame`s for school attendance zones
and district boundaries, and point and address lookups.

- It mirrors the R package in `~/projects/georgia-data-rpackage`
  (`georgiacivicdata` on CRAN-to-be): the same exported functions, without
  the `gcd_` prefix (`gcd.rows()` for `gcd_rows()`), the same arguments and
  the same output columns. The R package's `notes/function-design.md` is
  the design, with its reasoning.
- **Keep the two packages in parity, in both directions.** When this
  package changes or adds functionality (a new function, argument, column
  or behavior), the R package must get the same change, and when the R
  package changes or adds functionality, this package must follow. The
  only exceptions are the deliberate ones recorded in "Python and R
  differ" below; add any new one there with its reason. Because the R
  package is never edited from here, end any change here that the R
  package lacks by telling Shane exactly what the R package needs, and
  before working on a feature, check the R package for changes this
  package has not caught up with yet.
- The API's own guide is `~/projects/georgia-data/src/api/CLAUDE.md`
  (routes, parameters, errors, rate limits, privacy rules). Read it, and the
  code under `~/projects/georgia-data/src/api/`, for exact response shapes.
  **That repo is a separate project: never edit anything in
  `~/projects/georgia-data` or any service it runs.** Never edit the R
  package from here either.
- PyPI name `georgiacivicdata`; GitHub repo
  `shanejorr/georgia-data-pypackage`; docs at
  `https://georgiacivicdata.org/py/`.

## Commands

Run from the repo root. `uv` manages the environment (`uv sync --all-extras`
installs the package, both extras and every dependency group).

```bash
uv sync --all-extras
uv run pytest                                   # offline tests
uv run pytest --cov                             # coverage; keep >= 90%
uv run pytest --snapshot-update                 # rewrite syrupy snapshots (review the diff)
GCD_LIVE_TESTS=true uv run pytest tests/test_live.py   # live API (use sparingly)
uv run ruff check . && uv run ruff format --check .
uv run mypy                                     # strict
uv build && uvx twine check --strict dist/*     # sdist + wheel
uv run python docs/build.py                     # HTML + Markdown twins + llms.txt
uv run python docs/precompile.py                # re-execute the articles (live API)
```

The GitHub token for `gh` comes from `gh auth token`; never write it to a
file.

## Layout

| Path | Contents |
|---|---|
| `src/georgiacivicdata/__init__.py` | the public surface (`__all__`) |
| `_api.py` | base URL constant, URL builder, the one performer (user agent, retries, timeouts, the ETag disk cache, streaming to a file), the error-envelope parser |
| `_errors.py` | exception classes (`GCDError` and subclasses) and message formatting |
| `_messages.py` | `GCDAdvisory` warnings and stderr notes |
| `_options.py` | `set_option()`, `get_option()`, `option_context()`, backend resolution |
| `_cache.py` | session state `STATE`, cached metadata getter, disk cache folder, `cache_clear()` |
| `_schema.py` | schema fetching, `apply_schema_types()` (the one typing function), label relocation, dropping internal fields |
| `_frames.py` | JSON records to Arrow, Arrow to pandas or Polars, the metadata registry behind `meta()` |
| `_params.py` | query parameters: years, filters, missing and boolean encoding, `school_id`, the switch to `POST /query` |
| `_places.py` | the place-name resolver and name normalization |
| `_catalog.py`, `_describe.py` | find and understand data |
| `_rows.py`, `_values.py` | get data |
| `_dimension.py` | `dimension()` and the cached full lookup tables |
| `_zones.py` | zones, boundaries, zone status, zone coverage |
| `_locate.py`, `_geocode.py` | `locate()` and the Census batch geocoder |
| `_meta.py` | `meta()`, `citation()` |
| `tests/` | pytest; `helpers.py` (shared helpers), `conftest.py` (autouse fixtures), recorded responses in `tests/fixtures/m/`, syrupy snapshots in `tests/__snapshots__/` |
| `docs/` | Sphinx site: `conf.py`, `index.ipynb` and `articles/*.ipynb` (executed, committed), `notebooks/*.md` (their sources), `reference.md`, `agents.md`, `news.md`, `build.py`, `precompile.py` |
| `.github/workflows/` | `ci.yml` (lint, types, tests on a 3-OS matrix, no-extras job, build), `docs.yml` (builds and deploys to `gh-pages`), `live-api.yml` (weekly live tests), `publish.yml` (TestPyPI by hand, PyPI on a GitHub release) |

## Conventions

- Public functions keep the R names minus `gcd_`. Code arguments use the
  API's parameter names (`district_code`, `county_fips`, `detail`, `year`);
  name arguments (`district`, `school`, `county`) sit beside them. Filters
  are keyword arguments (`**filters`), the R `...`.
- Every table function takes a keyword-only `backend=None` (`"pandas"` or
  `"polars"`); `None` means the `backend` option, `"pandas"` by default.
  Typing overloads on `backend` give precise return types.
- Results are built as `pyarrow.Table`s, typed by `apply_schema_types()`,
  then converted once at the end (`_frames.to_frame()`). pandas output uses
  nullable dtypes: `Int64`, `boolean`, `string`; floats stay `float64`
  (`NaN`); dates `datetime64`; list columns hold Python lists. Polars gets
  the Arrow types directly.
- Types come from the schema, never guessed: codes are strings (leading
  zeros survive), `year` and `integer` columns int64 (float64 only when a
  value is not whole), `number` float64, `boolean` bool, proportions on the
  0-1 scale.
- Geometry is always a geopandas `GeoDataFrame` in WGS 84 (`geometry=True`).
  `backend="polars"` with geometry is an error pointing to
  `geometry=False`. geopandas is the `geo` extra; Polars the `polars` extra.
  Core dependencies: `httpx`, `pandas`, `platformdirs`, `pyarrow`. Every
  optional import is guarded with an install hint, and the no-extras CI job
  must pass.
- Names beside codes: every result that identifies a place carries its code
  and its name. Codes are always kept.
- **`sub_topic` is internal to the platform.** Never expose it as a
  parameter, column, printed field or documented concept. Drop `sub_topic`,
  `topic` and `key` from every result, `meta()` and `describe().raw`. Only
  `contract()` returns the contract verbatim.
- Errors: API errors are `GCDError` (or `GCDNotFoundError` for 404s,
  `GCDUnavailableError` for 5xx, 429 after retries and transport failures)
  with `code`, `status` and `details`. The resolver raises
  `GCDPlaceNotFoundError` / `GCDPlaceAmbiguousError`. Bad arguments raise
  `TypeError` / `ValueError` before any request.
- Messages: API advisories and search and zone notes are `GCDAdvisory`
  warnings (shown every time, pointing at the caller's line); progress notes
  (large downloads, rate-limit waits) go to stderr via `_messages.inform()`.
  Never `print()` elsewhere. `quiet=True` or `set_option("quiet", True)`
  silences both.
- Metadata: `meta(x)` reads a registry keyed by the object (Polars has no
  attributes); pandas results also carry `df.attrs["gcd_meta"]`. Keep meta
  values plain Python (no data frames inside: pandas compares `attrs` on
  `concat`).
- No base URL option: the URL is the constant `BASE_URL`.
- **ASCII-only source.** Write non-ASCII as `\uXXXX` escapes. Editing tools
  can expand escapes into raw characters (it happened while building: a
  tool decoded `\u00e9` in written content); `tests/test_meta_package.py`
  fails on any non-ASCII byte in the package, and re-escape test files the
  same way.
- Docstrings are NumPy style (Parameters, Returns, See Also, Examples).
  Examples that call the API carry `# doctest: +SKIP`.

## Python and R differ (on purpose)

- Function names drop `gcd_`; the import is `import georgiacivicdata as gcd`.
- `backend=` picks pandas or Polars; R always returns tibbles.
- `n_max=None` means all rows (R `Inf`); `year=range(2019, 2025)` is
  2019-2024 (Python ranges exclude the end).
- `None` as a filter value is ignored (R `NULL`); `None` inside a list
  selects missing values (R `NA`).
- `locate()` default ids are positions from 0 (R from 1).
- Integers are int64 throughout (R switches to double past
  `.Machine$integer.max`).
- `meta()` also returns the notes of `search()` (`confidence`, ...), the
  zone functions and `locate()` (`note`, `assignment_note`), which R keeps
  as attributes.
- Advisories are `GCDAdvisory` warnings, not `cli` messages; `search()` and
  `locate()` take `quiet`.
- The user agent is `georgiacivicdata-py/<version>`, so the platform's usage
  logs can tell the clients apart.

## API usage rules

- The API is production. **Every request counts in the platform's usage
  metric.** Tests replay recorded responses; live tests run weekly in CI.
- The recorded responses in `tests/fixtures/m/` came from the R package's
  httptest2 fixtures (same API, same requests). To add or re-record one,
  make the one small request with `httpx` (one district, one year, a few
  rows), save the body under `tests/fixtures/m/<test>/...`, check it is small
  and contains nothing personal, and mock it by URL in the test with
  `respx`. Synthetic responses (`helpers.json_response()`,
  `error_response()`) cover error envelopes, retries, 503s, CSV downloads
  and the Census upload.
- **Never commit a real home address** in code, tests, fixtures, examples or
  docs. Use public buildings (the Georgia State Capitol, 206 Washington St
  SW, Atlanta, GA 30334) and public landmarks.
- Location lookups (`POST /locate`, the Census geocoder) are never cached, in
  memory or on disk, and coordinates and addresses are never echoed in
  messages or errors. Addresses never reach the Georgia Civic Data API: they
  are geocoded with the Census batch geocoder and sent as points.

## Testing rules

- pytest; tests pass **offline**. The autouse `api` fixture wraps every test
  in `respx.mock(assert_all_mocked=True)`, so an unmocked request fails.
- The autouse `gcd_state` fixture resets the session cache and options, sets
  the disk cache to a temporary folder, removes retry waits, and seeds the
  list of lookup tables. The `tables` fixture seeds small lookup tables for
  the resolver and `locate()`.
- Snapshot tests (syrupy) for printed summaries; exact-string asserts for
  user-facing errors.
- Live tests in `tests/test_live.py` are marked `live` and run only with
  `GCD_LIVE_TESTS=true`.
- Guard optional packages with `pytest.importorskip()`.
- Nothing writes outside the temporary folders pytest provides.

## Release checklist

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
  `uv run pytest --cov` (>= 90%), the CI matrix green, the live workflow
  green, `uv run python docs/build.py` clean, `uv build` and
  `uvx twine check --strict dist/*`, `NEWS.md` updated, version bumped in
  `pyproject.toml`.
- **Never publish to PyPI or TestPyPI**: no `uv publish` or `twine upload`,
  no running `publish.yml`, no GitHub release. Shane decides when.
- Releases go through `.github/workflows/publish.yml` (trusted publishing,
  no API tokens). Each version can be uploaded to each index only once.
  1. One commit: the version in `pyproject.toml`, the `NEWS.md` heading
     (drop "unreleased"), and, for the first release, the install sections
     of `README.md`, `docs/notebooks/index.md` and `docs/index.ipynb`
     (`pip install georgiacivicdata` instead of the GitHub install). The
     push redeploys the docs at once, so release the same day.
  2. TestPyPI: `gh workflow run publish.yml`. It uploads to TestPyPI, then
     downloads the wheel back, installs it and imports it.
  3. PyPI: publish a GitHub release tagged `v<version>` (`v0.1.0`). The job
     stops if the tag doesn't match `pyproject.toml`.
- One-time setup, by Shane on pypi.org and test.pypi.org: a (pending)
  trusted publisher with owner `shanejorr`, repository
  `georgia-data-pypackage`, workflow `publish.yml`, and environment `pypi`
  or `testpypi`.

## Documentation site

- Sphinx with the PyData theme, MyST Markdown, myst-nb for the articles,
  autodoc + napoleon for the reference. `docs/build.py` builds the HTML,
  builds the same sources with `sphinx-markdown-builder`, copies each page's
  Markdown twin beside its HTML (`foo.html` and `foo.md`), adds a
  `<link rel="alternate" type="text/markdown">` to every page, and writes
  `llms.txt` (an index of the Markdown pages) and `llms-full.txt` (all of
  them in one file) at the site root. Keep all of that working: LLM agents
  read the docs as Markdown.
- Articles are precomputed, like the R vignettes: edit
  `docs/notebooks/<name>.md` (jupytext MyST notebooks), run
  `uv run python docs/precompile.py` locally (it calls the live API), and
  commit the executed `docs/articles/<name>.ipynb`. Sphinx never executes
  notebooks.
- **Never print a whole data frame or table in the docs.** Every output
  that shows one (a data frame, a Series, a `groupby().size()`, a
  crosstab) shows at most its first 5 rows: end the expression with
  `.head()`, or filter it to 5 rows or fewer first.
- Deployed by `.github/workflows/docs.yml` to the `gh-pages` branch, GitHub
  Pages at `https://shanejorr.github.io/georgia-data-pypackage/`, served at
  `https://georgiacivicdata.org/py/` by the main site (`~/projects/georgia-data`,
  Vercel), like the R docs at `/r/`: a rewrite in `web/next.config.ts`
  proxies `/py/*` to GitHub Pages, and `web/src/proxy.ts` redirects `/py` to
  `/py/`. The pages use relative links, so they only work with the trailing
  slash. `html_baseurl` sets canonical links to `/py/`.
- No custom domain on GitHub Pages and no `CNAME` on `gh-pages`: a custom
  domain would redirect `github.io` and break the rewrite.
- `CLAUDE.md` and `AGENTS.md` are not part of the site (`exclude_patterns`).

## When to flag Shane

Anything that changes what the package or the platform claims publicly (new
data coverage, privacy behavior, license wording, the site URL), so the
organization wiki's positioning note gets updated.

## Machine constraints

- `sudo` is interactive: never run it; give Shane the exact command.
- `/tmp` is a small shared tmpfs on the Linux box. If a build fails with
  "Disk quota exceeded", `mkdir -p ~/tmp-build` and set
  `TMPDIR=$HOME/tmp-build`.
- Shane monitors asynchronously (often from a phone): post short,
  self-contained progress updates; state blocking decisions up front.
- Shane works on two machines: commit and push often.
