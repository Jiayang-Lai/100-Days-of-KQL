# Day 5

It is not uncommon for tables to have string columns that need parsing, and this is where the parse operator shines.

# Official Document

[parse operator](https://learn.microsoft.com/en-us/kusto/query/parse-operator?view=microsoft-fabric)

# Note

parse is powerful as it provides various options for parsing strings into structured data. There are two similar operator called parse-where and parse-kv. parse-where is very similar to parse, but it filters out the strings that don't match the pattern. parse-kv is great for parsing key vault pair strings.
