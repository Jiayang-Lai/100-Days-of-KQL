# Day 10

make-series operator aggregates the values into a time series.

# Official Document

[make-series operator](https://learn.microsoft.com/en-us/kusto/query/make-series-operator?view=microsoft-fabric)

## Syntax

```T | make-series [MakeSeriesParameters] [Column =] Aggregation [default = DefaultValue] [, ...] on AxisColumn [from start] [to end] step step [by [Column =] GroupExpression [, ...]]```

# Note

This operator is great for performing over-the-time analysis.
