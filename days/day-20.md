# Day 20

hash() scalar function generates a hash for the input value.

# Official Document

[hash()](https://learn.microsoft.com/en-us/kusto/query/hash-function?view=microsoft-fabric)

# Note

This function is helpful for generating hash for longer content to increase query performance as a usable identifier. This function uses xxhash64 algorithm, to generate other hash values here are other functions:

- hash_md5()
- hash_sha1()
- hash_sha256()
- hash_xxhash64()
