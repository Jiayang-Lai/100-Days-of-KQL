# Day 10

iff() scalar function plays an essential role in parser.

# Official Document

[iff()](https://learn.microsoft.com/en-us/kusto/query/iff-function?view=microsoft-fabric)

# Note

When writing user defined functions for parsing HTTP data collector API ingested tables, due to ingestion logic the schema can vary and cause certain columns to have different names. Therefore, iff() allows us to return desired values based on specified condition.
