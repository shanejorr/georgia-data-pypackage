# georgiacivicdata

[![CI](https://github.com/shanejorr/georgia-data-pypackage/actions/workflows/ci.yml/badge.svg)](https://github.com/shanejorr/georgia-data-pypackage/actions/workflows/ci.yml)
[![Docs](https://github.com/shanejorr/georgia-data-pypackage/actions/workflows/docs.yml/badge.svg)](https://georgiacivicdata.org/py/)

`georgiacivicdata` brings Georgia's public data into Python. It is the
Python client for the API run by [Georgia Civic Data](https://georgiacivicdata.org).

Georgia Civic Data gathers, organizes, and standardizes Georgia's public
data, helping residents, parents, researchers, and professionals find
answers in data that is already theirs. Every dataset has the same shape,
with the same codes for counties, school districts, schools and
demographic groups, so datasets from different agencies can be compared
and joined.

The data covers education, Census, health, and immigration, from the whole
state down to single schools and Census tracts. Each dataset comes with a
data contract that documents its source, its columns, and the limits of the
data.

With `georgiacivicdata` you can:

- Find Georgia datasets, read their documentation, and get rows, all from
  Python.
- Get **pandas or Polars** data frames with consistent column types: codes
  stay text so leading zeros survive, years are integers, and rates are
  proportions between 0 and 1.
- See every school, district, and county code with its name, and filter by
  name instead of code.
- Get school attendance zones and district boundaries as geopandas
  `GeoDataFrame`s, ready to map.
- Look up the schools zoned for any Georgia address.

There is no API key and nothing to configure. The package mirrors the R
package [georgiacivicdata](https://georgiacivicdata.org/r/): the same
functions, without the `gcd_` prefix.

## Installation

The package is not on PyPI yet. Install the development version from
GitHub:

```bash
pip install "georgiacivicdata @ git+https://github.com/shanejorr/georgia-data-pypackage"
```

Extras add Polars and geopandas:

```bash
pip install "georgiacivicdata[polars,geo] @ git+https://github.com/shanejorr/georgia-data-pypackage"
```

## Example: graduation rates in Fulton County

How has the high school graduation rate in Fulton County Schools changed
over time? The usual workflow:

```python
import georgiacivicdata as gcd

# 1. Find a dataset by plain words
gcd.search("high school graduation", n=5)[["name", "title", "year_min", "year_max"]]

# 2. Learn what is in it
gcd.columns("graduation_rate_4_year_cohort")[["column", "type", "role", "unit"]]
gcd.describe("graduation_rate_4_year_cohort")   # source, years, notes

# 3. Get the rows: names turn into codes for you
grads = gcd.rows(
    "graduation_rate_4_year_cohort",
    district="Fulton County",
    detail="districts",
    demographic=["all", "black", "hispanic", "white"],
    year=range(2011, 2026),
)

# 4. Plot the overall rate
grads[grads["demographic"] == "all"].plot(x="year", y="graduation_rate")

# 5. Cite it
gcd.citation(grads)
```

Each place comes back with both its code and its name. A missing value
usually means the figure was **suppressed** to protect small groups, not
that it is zero. The API's advisories arrive as `GCDAdvisory` warnings: for
example, never add the `all` total to its subgroups.

### pandas or Polars

pandas is the default. Ask for Polars per call, or for the session:

```python
gcd.rows("employment", year=2024, backend="polars")
gcd.set_option("backend", "polars")
```

## Lookup tables

Everything known about a place beyond its name lives in lookup tables: a
school's level, locale, grade span, address and coordinates, a tract's
population. `gcd.dimension()` returns one:

```python
gcd.dimension("schools", district="Fulton County", school_level="high", active=True)
```

## School zones and places

```python
zones = gcd.school_zones(district="Atlanta Public Schools", zone_level="high")
zones.plot(column="school_name")

# The Georgia State Capitol: its county, tract, district and zoned schools
gcd.locate(address="206 Washington St SW, Atlanta, GA 30334")
```

Addresses are geocoded on your computer with the U.S. Census geocoder, so
only the point reaches the Georgia Civic Data API.

## Documentation

- Package website: <https://georgiacivicdata.org/py/>
- Every page also has a Markdown version for LLM agents: add `.md` to its
  address, or start at <https://georgiacivicdata.org/py/llms.txt>.
- API documentation: <https://georgiacivicdata.org/docs>

## Data license and citation

The data is published under the [Creative Commons Attribution 4.0
International license (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/):
credit Georgia Civic Data and the original source. `gcd.citation()` writes
the citation for any result. The package code is MIT-licensed.
