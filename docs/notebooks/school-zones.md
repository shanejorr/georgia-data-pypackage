---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# School zones and places

Georgia Civic Data publishes school attendance zones: the areas that assign
a home to its zoned elementary, middle and high school. This article maps
one district's zones, checks which schools have no zone and how precise the
zones are, and finds the places a location falls in.

The geometry functions return geopandas `GeoDataFrame`s, so install the
`geo` extra (`pip install georgiacivicdata[geo]`) to map them. For plain
tables, use `geometry=False`.

```{code-cell} ipython3
:tags: [remove-cell]

import warnings

import pandas as pd

warnings.formatwarning = lambda message, category, *args, **kwargs: (
    f"{category.__name__}: {message}\n"
)
pd.set_option("display.width", 100)
pd.set_option("display.max_columns", 10)
pd.set_option("display.max_colwidth", 60)
```

```{code-cell} ipython3
import matplotlib.pyplot as plt
import pandas as pd

import georgiacivicdata as gcd
```

## Map one district's zones

```{code-cell} ipython3
zones = gcd.school_zones(district="Atlanta Public Schools")
zones.groupby(["zone_level", "method", "accuracy_class"]).size()
```

```{code-cell} ipython3
fig, axes = plt.subplots(1, 3, figsize=(9, 3.4))
for ax, level in zip(axes, ["elementary", "middle", "high"]):
    zones[zones["zone_level"] == level].plot(
        ax=ax, column="school_name", cmap="tab20", edgecolor="white", linewidth=0.2
    )
    ax.set_title(level)
    ax.set_axis_off()
fig.suptitle("Atlanta Public Schools attendance zones, 2026-27")
plt.show()
```

Each colour is a school. The default `resolution="display"` returns
simplified polygons for maps. `resolution="full"` returns the source
polygons, which are much larger; filter to a district before asking for
them.

## Schools without a zone

Charter, magnet, alternative and virtual schools have no attendance zone.
`gcd.school_zone_status()` says which schools have one and why the others
don't:

```{code-cell} ipython3
status = gcd.school_zone_status(district="Atlanta Public Schools")
status["zone_status"].value_counts()
```

The schools with no zone, by reason:

```{code-cell} ipython3
status.loc[status["zone_status"] == "no_zone", "no_zone_category"].value_counts().head()
```

```{code-cell} ipython3
print(gcd.meta(status)["note"])
```

## How precise are the zones?

Zones come from very different sources. Some are the district's official GIS
layers; others are digitized from PDF maps, rebuilt from street lists, or
are the whole district outline (in districts with one school per grade).
Every zone says how it was built (`method`) and how exact it is
(`accuracy_class`); treat them accordingly.

```{code-cell} ipython3
coverage = gcd.school_zone_coverage()
pd.crosstab(coverage["level_status"], coverage["zone_level"])
```

`gcd.school_zone_coverage()` gives one row per district and level, with the
share of the district's land and 2020 population its zones cover, and the
reason for anything short of complete:

```{code-cell} ipython3
coverage.loc[
    coverage["district_name"] == "Appling County",
    ["zone_level", "level_status", "pct_population", "methods", "reason"],
]
```

## Locate a place

`gcd.locate()` takes points (`lat`, `lon`) or street addresses and returns
the county, Census tract and block group, school district and zoned schools
each falls in, one row per place.

```{code-cell} ipython3
landmarks = pd.DataFrame(
    {
        "landmark": [
            "Georgia State Capitol",
            "Stone Mountain Park",
            "Okefenokee Swamp Park",
            "Appling County Courthouse",
        ],
        "lat": [33.7490, 33.8053, 31.0558, 31.7782],
        "lon": [-84.3880, -84.1455, -82.2701, -82.3482],
    }
)
places = gcd.locate(lat=landmarks["lat"], lon=landmarks["lon"], id=landmarks["landmark"])
places[["id", "geographic_type", "geographic_id", "geographic_name", "grades"]].head()
```

The output is long (`head()` shows its first five rows): filter it to the
rows you need, such as `places[places["geographic_type"] == "high_school"]`. A school's
`geographic_id` is its `"DISTRICT-SCHOOL"` code, the form `gcd.rows()` takes
as `school_id`.

The `note` column explains any row that is missing or needs care, such as a
level with no zone collected yet:

```{code-cell} ipython3
noted = places[places["note"].notna()]
noted[["id", "geographic_type", "geographic_name"]]
```

```{code-cell} ipython3
import textwrap

for note in noted["note"]:
    print(textwrap.fill(note, width=76), end="\n\n")
```

### Addresses

Addresses are geocoded on your computer with the U.S. Census batch geocoder;
only the resulting coordinates are sent to Georgia Civic Data. Give one-line
addresses or a data frame with `street`, `city`, `state` and `zip`:

```{code-cell} ipython3
capitol = gcd.locate(address="206 Washington St SW, Atlanta, GA 30334")
capitol[["match_status", "matched_address", "geographic_type", "geographic_name", "grades"]].head()
```

The same lookup for several buildings, from a data frame with one column per
address part. `id` carries each building's name into the output:

```{code-cell} ipython3
buildings = pd.DataFrame(
    {
        "building": ["Georgia State Capitol", "Savannah City Hall"],
        "street": ["206 Washington St SW", "2 E Bay St"],
        "city": ["Atlanta", "Savannah"],
        "state": ["GA", "GA"],
        "zip": ["30334", "31401"],
    }
)
located = gcd.locate(address=buildings, id=buildings["building"], quiet=True)
located.loc[
    located["geographic_type"] == "high_school",
    ["id", "match_status", "geographic_name", "grades"],
]
```

### Overlapping school zones

Some residences are zoned to one elementary school for the early grades and
another for the later ones. In this case, a level has more than one school
row and `grades` tells them apart. City Schools of Decatur, for example,
splits elementary schools between K-2 and 3-5, so some homes in the district
show two elementary schools:

```{code-cell} ipython3
oakhurst = gcd.dimension(
    "schools",
    district_code="773",
    q="Oakhurst",
    active=True,
    columns=["school_name", "latitude", "longitude"],
)
oakhurst
```

```{code-cell} ipython3
split = gcd.locate(lat=oakhurst["latitude"], lon=oakhurst["longitude"], quiet=True)
split.loc[
    split["geographic_type"].str.endswith("_school"),
    ["geographic_type", "geographic_id", "geographic_name", "grades"],
]
```

`grade` keeps only the school for one grade:

```{code-cell} ipython3
one_grade = gcd.locate(lat=oakhurst["latitude"], lon=oakhurst["longitude"], grade=4, quiet=True)
one_grade.loc[
    one_grade["geographic_type"].str.endswith("_school"),
    ["geographic_type", "geographic_name", "grades"],
]
```

### The default assignment

A zone is the default assignment, not the only option:

```{code-cell} ipython3
print(gcd.meta(capitol)["assignment_note"])
```

Students can attend another public school by transfer, or a charter, magnet,
or other choice school option. See Georgia Civic Data's article [School
Zones and School Choice in
Georgia](https://georgiacivicdata.org/stories/school-attendance-rules) for
more information.
