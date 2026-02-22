# Day 22

materialize() is a special function that captures the value of a tabular expression, serving the result as a cache that does not require multiple recalculations.

# Official Document

[materialize()](https://learn.microsoft.com/en-us/kusto/query/materialize-function?view=microsoft-fabric)

# Note

This function is recommended when a value defined by let statement will be used in the query more than once.
