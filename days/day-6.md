# Day 6

getschema operator returns the tabular schema of the input.

# Official Document

[getschema operator](https://learn.microsoft.com/en-us/kusto/query/getschema-operator?view=microsoft-fabric)

# Note

From a quick glance this operator might seem not very helpful, but as the query grows in complexity getschema would help troubleshooting greatly. In Sentinel, a JSON string could be either string or dynamic type in table, if the column is string type `parse_json()` function needs to be used before accessing property. With getschema the column type is easily shown.
