Write a KQL query that uses the `.show queries` command to list the 5 most recent failed queries, including the failure reason, query and helpful stats.

# .show queries command - Kusto

The `.show``queries` command lists queries on the cluster that have reached a final state, and that the user invoking the command has access to see. Optionally, the command can return queries that are still running, queries by specific users, or queries grouped by user. To see both queries and commands completion, use [.show queries-and-commands](commands-and-queries).

The `.show``queries` command lists queries on the eventhouse that have reached a final state, and that the user invoking the command has access to see. Optionally, the command can return queries that are still running, queries by specific users, or queries grouped by user. To see both queries and commands completion, use [.show queries-and-commands](commands-and-queries).

## Syntax

`.show``queries`

`.show``running``queries` [ `by user`*UserPrincipalName*]

Learn more about [syntax conventions](/en-us/kusto/query/syntax-conventions).

## Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| *UserPrincipalName* | `string` |  | The UPN of a specific user for which to return a list of queries. |

## Returns

- Returns a table containing previously run queries across all databases in the cluster and their completion statistics. You can use KQL queries to explore the results.
- Returns a list of currently executing queries by the current user, or by another user, or by all users.

Note: The text of the query is truncated after 64 KB.

The returned table schema is:

| ColumnName | ColumnType | Description |
| --- | --- | --- |
| ClientActivityId | `string` | Client ID of the request |
| Text | `string` | Query text, truncated at 64 KB |
| Database | `string` | Name of the database on which the query was executed |
| StartedOn | `datetime` | Timestamp when query execution started |
| LastUpdatedOn | `datetime` | Timestamp of the last status update |
| Duration | `timespan` | Server-side query duration |
| State | `string` | Completion state |
| RootActivityId | `guid` | Server-side request ID |
| User | `string` | User ID that ran the query |
| FailureReason | `string` | Failure reason. If query succeeded, this field is empty. |
| TotalCpu | `timespan` | Total CPU consumed by the query |
| CacheStatistics | `dynamic` | Data-cache usage statistics |
| Application | `string` | Name of the application that was used to run the query |
| MemoryPeak | `long` | Peak memory statistics |
| ScannedExtentsStatistics | `dynamic` | Statistics of the scanned shards (extents) |
| Principal | `string` | AAD-ID of the user or application that was used to run the query |
| ClientRequestProperties | `dynamic` | Client request properties |
| ResultSetStatistics | `dynamic` | Statistics describing returned dataset |
| WorkloadGroup | `string` | Name of the workload group that query was associated with |

## Examples

### Show completed queries

```kusto
.show queries 
| project Text, Duration
| take 10
```

**Output**

| Text | Duration |
| --- | --- |
| StormEvents | sort by DeathsDirect desc | 00:00:00.2343761 |
| StormEvents | sort by DeathsDirect desc | 00:00:00.2187503 |
| StormEvents | sort by DeathsDirect desc | 00:00:00.2343115 |
| StormEvents | sort by DamageProperty desc | 00:00:00.2656510 |
| StormEvents | sort by StartTime desc | 00:00:00.2343012 |
| StormEvents | sort by StartTime desc | 00:00:00.2813042 |
| StormEvents | sort by StartTime desc | 00:00:00.3594493 |
| TestFunction(5) | 00:00:00.0312024 |
| traceAgg(now(5500d)) | 00:00:00.0312952 |
| traceAgg(now(-5500d)) | 00:00:00.0312445 |

### Show running queries by the current user

```kusto
.show running queries 
```

### Show running queries by a specified user

```kusto
.show running queries by user <UserPrincipalName>
```

