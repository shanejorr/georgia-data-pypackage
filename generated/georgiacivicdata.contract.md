# georgiacivicdata.contract

### georgiacivicdata.contract(name, file=None)

Get a dataset's data contract.

The dataset's formal, versioned contract in the Open Data Contract
Standard (ODCS v3.2): its schema, quality rules, `version` and
`schema_hash`. For data engineers building pipelines and anyone citing
the exact schema. Most users want [`describe()`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe) instead.

Datasets and the `school_attendance_zones` geometry dataset have
contracts; lookup tables and `school_district_boundaries` do not.

* **Parameters:**
  * **name** (*str*) -- A dataset name.
  * **file** (*str* *or* *path-like* *,* *optional*) -- If given, the contract is written there verbatim as YAML and the path
    is returned. Default: return the contract as a dict.
* **Returns:**
  *dict or path* -- The contract as a nested dict (parsed from its JSON form), or, with
  `file`, the path.

#### SEE ALSO
[`describe`](https://georgiacivicdata.org/py/generated/georgiacivicdata.describe.md#georgiacivicdata.describe)
: a readable summary.

### Examples

```pycon
>>> import georgiacivicdata as gcd
>>> spec = gcd.contract("graduation_rate_4_year_cohort")
>>> spec["version"]
>>> gcd.contract("graduation_rate_4_year_cohort", file="contract.yaml")
```
