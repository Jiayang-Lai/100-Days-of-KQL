# Day 30

Today's query is for The Mini Shai-Hulud Campaign.

# Note

Third wave of the Shai-Hulud supply chain campaign hit npm, PyPI, and Packagist simultaneously over 48 hours in April 2026, compromising ~1,800 repositories with 930k+ weekly downloads. Threat actor TeamPCP stole credentials at scale, but this iteration introduced three detection-critical innovations:

**AI Agent Persistence**: Malware embeds hooks into `.claude/settings.json` (Claude Code SessionStart) and `.vscode/tasks.json` (VSCode folderOpen), signed as `claude@users.noreply.github.com` with benign commit messages ("chore: update dependencies"). This is one of the first supply chain attacks weaponizing IDE/AI tool configurations—opening a compromised repo in VSCode or Claude Code silently re-executes the payload. Both file paths should trigger alerts.

**Geofence Evasion**: If system locale is Russian, the payload logs "Exiting as russian language detected!" and exits cleanly. This CIS exemption is a known pattern of Eastern European operators and suggests Russia/CIS-based threat actors.

**Encrypted Exfiltration**: Unlike previous waves, stolen secrets are encrypted with AES-256-GCM and wrapped with RSA-4096 using an embedded public key. Defenders discovering dead-drop repos only see ciphertext, forcing assumption of worst-case compromise.

**Detection anchors**: Look for workflow injection via `dependabout/github_actions/format/setup-formatter` branches, GitHub PAT and npm token regex matches in code, and the distinctive Bun runtime version 1.3.13. IDE persistence files and the exfil repo naming pattern (Dune-themed regex with "Shai-Hulud" in description) are strong signals.

# Gen AI Time

The workflow ran for 2 attempt(s) and finished with `criteria_met=True`. The final accepted attempt was 2.

## Attempt 1

This attempt generated 5 query candidate(s) and executed 5 candidate(s). The attempt did not pass evaluation. All five query candidates failed due to schema mismatches with the available tables in the mock Sentinel logs: **Candidate 1 (Comprehensive Multi-Indicator)**: Failed with "Failed to resolve scalar expression named 'M...

### Prompt

Please find the prompt from this [file](day-30.prompt.md).

### Result

- Candidate 1 failed to execute: Request is invalid and cannot be processed: Semantic error: SEM0100: 'project' operator: Failed to resolve scalar expression named 'MD5'
- Candidate 2 failed to execute: Request is invalid and cannot be processed: Semantic error: SEM0100: 'project' operator: Failed to resolve scalar expression named 'MD5'
- Candidate 3 failed to execute: Request is invalid and cannot be processed: Semantic error: SEM0100: 'where' operator: Failed to resolve scalar expression named 'ProcessVersionInfoProductVersion'
- Candidate 4 failed to execute: Request is invalid and cannot be processed: Semantic error: SEM0100: 'project' operator: Failed to resolve scalar expression named 'InitiatingProcessCommandLine'
- Candidate 5 failed to execute: Request is invalid and cannot be processed: Semantic error: SEM0100: 'where' operator: Failed to resolve table or column expression named 'DeviceEvents'

Evaluator feedback:

All five query candidates failed due to schema mismatches with the available tables in the mock Sentinel logs:

**Candidate 1 (Comprehensive Multi-Indicator)**: Failed with "Failed to resolve scalar expression named 'MD5'" - DeviceFileEvents mock data does not include MD5 field.

**Candidate 2 (File-Based IOC)**: Same failure - attempted to project MD5 field from DeviceFileEvents, which only provides SHA256, FileSize, FileName, FolderPath, and related metadata.

**Candidate 3 (Process Execution)**: Failed with "Failed to resolve scalar expression named 'ProcessVersionInfoProductVersion'" - DeviceProcessEvents mock data lacks version info fields; only contains ProcessId, ProcessCommandLine, FileName, FolderPath, ActionType, and initiating process metadata.

**Candidate 4 (Network Detection)**: Failed with "Failed to resolve scalar expression named 'InitiatingProcessCommandLine'" - DeviceNetworkEvents mock data does not include InitiatingProcessCommandLine; available fields are RemoteUrl, RemoteIP, RemotePort, Protocol, ActionType, and basic initiating process identifiers.

**Candidate 5 (Dead-Drop Repository)**: Failed with "Failed to resolve table or column expression named 'DeviceEvents'" - This table does not exist in the mock Sentinel schema. Repository metadata would need to come from git-related tables (not provided) or be queried differently.

**Main Gaps**:
1. Schema mismatch: Queries reference fields not present in available tables (MD5, ProcessVersionInfoProductVersion, InitiatingProcessCommandLine in network events).
2. Missing tables: No DeviceEvents table; no git commit, repository metadata, or workflow-specific tables.
3. Field availability: DeviceNetworkEvents lacks process command-line context; DeviceFileEvents lacks process version details.
4. Regex matching on unsuitable columns: Dead-drop pattern detection attempted on non-existent fields.

**Required Refinements**:
- Use only available fields from mock tables: DeviceFileEvents (SHA256, FileName, FolderPath, FileSize, ActionType, InitiatingProcessFileName/AccountName), DeviceProcessEvents (ProcessCommandLine, FileName, InitiatingProcessCommandLine, AdditionalFields), DeviceNetworkEvents (RemoteUrl, RemoteIP, Protocol, InitiatingProcessFileName), DeviceInfo (OSPlatform, AdditionalFields for locale detection).
- Remove projections and filters on non-existent fields (MD5, ProcessVersionInfoProductVersion, InitiatingProcessCommandLine in network context).
- Leverage AdditionalFields JSON in DeviceProcessEvents for environment variable (__DAEMONIZED) and cryptographic constant detection.
- Focus on file path regex matching for dead-drop patterns rather than process command lines.
- Simplify to core IOCs: hash matching, suspicious file paths, process execution patterns, network endpoints, and environment variable detection.

KQL generation stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 19762 |
| Output     | 4234 |
| Total      | 23996 |

Evaluation stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 15652 |
| Output     | 1900 |
| Total      | 17552 |

These are the queries we got:

```kql
// Mini Shai-Hulud Campaign Detection - Comprehensive Multi-Indicator Query
// Detects supply chain attack artifacts across file, process, network, and environment IOCs
// Covers April 29-30, 2026 incident and ongoing persistence mechanisms
let LoaderHash = "4066781fa830224c8bbcc3aa005a396657f9c8f9016f9a64ad44a9d7f5f45e34";
let PayloadHash1 = "80a3d2877813968ef847ae73b5eeeb70b9435254e74d7f07d8cf4057f0a710ac";
let PayloadHash2 = "6f933d00b7d05678eb43c90963a80b8947c4ae6830182f89df31da9f568fea95";
let SuspiciousFilePaths = dynamic(["setup.mjs", "execution.js", ".claude/settings.json", ".vscode/tasks.json"]);
let DuneTerm = "(sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)";
let DeadDropPattern = @"(sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\d{1,3}";
let BunVersion = "1.3.1313";
let SuspiciousEmails = dynamic(["claude@users.noreply.github.com", "dependabot[bot]@users.noreply.github.com"]);
let C2Domains = dynamic(["api.github.com", "registry.npmjs.org"]);
let CryptoSalt = "ctf-scramble-v2";
let PBKDF2Key1 = "5012caa5847ae9261dfa16f91417042f367d6bed149c3b8af7a50b203a093007";
let EvasionString = "Exiting as russian language detected!";
let fileIOCs = DeviceFileEvents
| where TimeGenerated >= ago(90d)
| where SHA256 in (LoaderHash, PayloadHash1, PayloadHash2)
  or FileName in (SuspiciousFilePaths)
  or (FolderPath contains ".claude" or FolderPath contains ".vscode")
  or FileSize == 12159795 and FileName == "execution.js"
| project TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, SHA256, MD5, FileSize, 
  InitiatingProcessFileName, InitiatingProcessCommandLine, ActionType, 
  InitiatingProcessAccountName, InitiatingProcessAccountDomain, EventType = "FileIOC";
let processIOCs = DeviceProcessEvents
| where TimeGenerated >= ago(90d)
| where (FileName in ("setup.mjs", "execution.js") or ProcessCommandLine contains "setup.mjs" or ProcessCommandLine contains "execution.js")
  or (ProcessVersionInfoProductVersion contains BunVersion or InitiatingProcessVersionInfoProductVersion contains BunVersion)
  or (InitiatingProcessCommandLine contains "node .claude/setup.mjs" or InitiatingProcessCommandLine contains "node .vscode/setup.mjs")
  or (ProcessCommandLine contains "folderOpen" or ProcessCommandLine contains "SessionStart")
| project TimeGenerated, DeviceId, DeviceName, FileName, ProcessCommandLine, 
  ProcessVersionInfoProductVersion, InitiatingProcessFileName, 
  InitiatingProcessAccountName, AccountName, ProcessId, EventType = "ProcessIOC";
let networkIOCs = DeviceNetworkEvents
| where TimeGenerated >= ago(90d)
| where (RemoteUrl in (C2Domains) or RemoteUrl contains "github.com" or RemoteUrl contains "npmjs.org")
  or (RemoteUrl matches regex @"https://registry\.npmjs\.org/")
| project TimeGenerated, DeviceId, DeviceName, RemoteUrl, RemoteIP, RemotePort, 
  InitiatingProcessFileName, InitiatingProcessCommandLine, Protocol, ActionType, EventType = "NetworkIOC";
let envIOCs = DeviceEvents
| where TimeGenerated >= ago(90d)
| where (RegistryValueName == "__DAEMONIZED" or InitiatingProcessCommandLine contains "__DAEMONIZED")
  or AdditionalFields contains "__DAEMONIZED"
  or AdditionalFields contains CryptoSalt
  or AdditionalFields contains PBKDF2Key1
  or AdditionalFields contains EvasionString
| project TimeGenerated, DeviceId, DeviceName, InitiatingProcessCommandLine, 
  RegistryKey, RegistryValueName, RegistryValueData, EventType = "EnvironmentIOC";
let stringIOCs = DeviceEvents
| where TimeGenerated >= ago(90d)
| where InitiatingProcessCommandLine contains CryptoSalt
  or InitiatingProcessCommandLine contains PBKDF2Key1
  or InitiatingProcessCommandLine contains EvasionString
  or AdditionalFields contains "gh[op]_[A-Za-z0-9]{36}"
  or AdditionalFields contains "npm_[A-Za-z0-9]{36,}"
  or InitiatingProcessCommandLine matches regex @"gh[op]_[A-Za-z0-9]{36}"
| project TimeGenerated, DeviceId, DeviceName, InitiatingProcessCommandLine, 
  InitiatingProcessAccountName, InitiatingProcessFileName, EventType = "CredentialIOC";
let ruLocale = DeviceInfo
| where OSPlatform contains "Windows" or OSPlatform contains "Linux"
| where OSVersionInfo contains "Russian" or OSPlatform contains "ru"
| project DeviceId, DeviceName, OSPlatform, OSVersionInfo, RiskIndicator = "RussianLocale";
union fileIOCs, processIOCs, networkIOCs, envIOCs, stringIOCs
| join kind=leftouter (ruLocale) on DeviceId
| project TimeGenerated, DeviceId, DeviceName, EventType, FileName, ProcessCommandLine, 
  RemoteUrl, InitiatingProcessAccountName, RiskIndicator, ActionType
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud File-Based Detection Query
// Focuses on malware artifacts, IDE configuration files, and persistence indicators
let LoaderHash = "4066781fa830224c8bbcc3aa005a396657f9c8f9016f9a64ad44a9d7f5f45e34";
let PayloadHash1 = "80a3d2877813968ef847ae73b5eeeb70b9435254e74d7f07d8cf4057f0a710ac";
let PayloadHash2 = "6f933d00b7d05678eb43c90963a80b8947c4ae6830182f89df31da9f568fea95";
DeviceFileEvents
| where TimeGenerated >= ago(90d)
| where SHA256 in (LoaderHash, PayloadHash1, PayloadHash2)
  or (FileName == "setup.mjs" and FolderPath contains ".claude")
  or (FileName == "setup.mjs" and FolderPath contains ".vscode")
  or (FileName == "settings.json" and FolderPath contains ".claude")
  or (FileName == "tasks.json" and FolderPath contains ".vscode")
  or (FileName == "execution.js" and FolderPath contains ".claude" and FileSize == 12159795)
| project TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, FileSize, SHA256, MD5,
  InitiatingProcessFileName, InitiatingProcessCommandLine, ActionType, 
  InitiatingProcessAccountName, InitiatingProcessAccountDomain
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud Process Execution Detection
// Detects suspicious process execution, Bun runtime abuse, and hook-based execution
let BunVersion = "1.3.1313";
let SuspiciousPatterns = dynamic(["setup.mjs", "execution.js", ".claude/setup.mjs", ".vscode/setup.mjs"]);
DeviceProcessEvents
| where TimeGenerated >= ago(90d)
| where (FileName == "setup.mjs" or FileName == "execution.js")
  or ProcessCommandLine contains "node .claude/setup.mjs"
  or ProcessCommandLine contains "node .vscode/setup.mjs"
  or ProcessCommandLine contains "folderOpen"
  or ProcessCommandLine contains "SessionStart"
  or ProcessVersionInfoProductVersion contains BunVersion
  or InitiatingProcessVersionInfoProductVersion contains BunVersion
  or InitiatingProcessFileName =~ "(bun|node)" and ProcessCommandLine contains "setup"
| project TimeGenerated, DeviceId, DeviceName, FileName, ProcessCommandLine, ProcessId,
  ProcessVersionInfoProductVersion, InitiatingProcessFileName, InitiatingProcessCommandLine,
  InitiatingProcessAccountName, InitiatingProcessCreationTime, AccountName
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud Network Detection Query
// Identifies C2 communications and package manager abuse
let C2Domains = dynamic(["api.github.com", "registry.npmjs.org"]);
let SuspiciousPatterns = dynamic(["dependabout/github_actions/format/setup-formatter", "format-check.yml", "format-results"]);
DeviceNetworkEvents
| where TimeGenerated >= ago(90d)
| where (RemoteUrl contains "api.github.com" or RemoteUrl contains "registry.npmjs.org")
  or RemoteUrl matches regex @"https://registry\.npmjs\.org/"
  or InitiatingProcessFileName =~ "(npm|python|composer|node)"
  and (RemoteUrl contains "github.com" or RemoteUrl contains "npmjs.org")
| project TimeGenerated, DeviceId, DeviceName, RemoteUrl, RemoteIP, RemotePort,
  InitiatingProcessFileName, InitiatingProcessCommandLine, Protocol, ActionType,
  InitiatingProcessAccountName, InitiatingProcessCreationTime
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud Dead-Drop Repository Detection
// Searches for exfiltration repositories matching Dune-themed naming pattern
let DeadDropPattern = @"(sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\d{1,3}";
DeviceEvents
| where TimeGenerated >= ago(90d)
| where InitiatingProcessCommandLine matches regex DeadDropPattern
  or FolderPath matches regex DeadDropPattern
  or AdditionalFields contains "Mini Shai-Hulud has Appeared"
  or FileName matches regex DeadDropPattern
| project TimeGenerated, DeviceId, DeviceName, FolderPath, FileName, InitiatingProcessCommandLine,
  InitiatingProcessAccountName, AdditionalFields
| sort by TimeGenerated desc
```

## Attempt 2

This attempt generated 9 query candidate(s) and executed 9 candidate(s). The evaluator accepted this attempt. ## Evaluation Summary: Mini Shai-Hulud KQL Detection Queries **STATUS: SUCCESS** ✓ All nine candidate queries executed successfully against the mock Sentinel logs without schema errors, and queries 1-8 returned meanin...

### Prompt

~~~markdown
## Refined KQL Detection Query Generation Request for Mini Shai-Hulud Campaign

Generate corrected KQL detection queries for the Mini Shai-Hulud supply chain attack using ONLY the available table fields from Sentinel mock logs:

### Available Schema
- **DeviceFileEvents**: TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, FileSize, SHA256, ActionType, InitiatingProcessFileName, InitiatingProcessId, InitiatingProcessAccountName, InitiatingProcessAccountDomain
- **DeviceProcessEvents**: TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, ActionType, ProcessId, ProcessCommandLine, ProcessCreationTime, InitiatingProcessFileName, InitiatingProcessId, InitiatingProcessAccountName, InitiatingProcessAccountDomain, **AdditionalFields (JSON with environment variables)**
- **DeviceNetworkEvents**: TimeGenerated, DeviceId, DeviceName, InitiatingProcessFileName, InitiatingProcessId, InitiatingProcessAccountName, InitiatingProcessAccountDomain, RemoteUrl, RemoteIP, RemotePort, LocalIP, LocalPort, Protocol, ActionType
- **DeviceInfo**: TimeGenerated, DeviceId, DeviceName, OSPlatform, OSVersion, OSBuild, OSArchitecture, MachineGroup, OnboardingStatus, SensorHealthState, **AdditionalFields (JSON with LANG/LC_ALL locale settings)**

### Corrected Detection Requirements
1. **File Hashes**: Match SHA256 hashes in DeviceFileEvents for loader (4066781fa830224c8bbcc3aa005a396657f9c8f9016f9a64ad44a9d7f5f45e34) and payloads (80a3d2877813968ef847ae73b5eeeb70b9435254e74d7f07d8cf4057f0a710ac, 6f933d00b7d05678eb43c90963a80b8947c4ae6830182f89df31da9f568fea95)
2. **Suspicious Files**: Detect .claude/execution.js (FileSize ~12,150,784), .vscode/tasks.json, .claude/settings.json via FolderPath/FileName matching
3. **Process Execution**: Match ProcessCommandLine patterns for "node .claude/setup.mjs", "node .vscode/setup.mjs", "bun run", "setup.mjs", "execution.js"
4. **Network IOCs**: Match RemoteUrl containing "api.github.com", "registry.npmjs.org" or specific exfiltration repo names (sardaukar-sandworm-*, mentat-ornithopter-*, etc.)
5. **Environment Indicators**: Use AdditionalFields (JSON parsing) in DeviceProcessEvents to detect __DAEMONIZED environment variable and cryptographic constants (ctf-scramble-v2, PBKDF2 keys, evasion strings)
6. **Locale Attribution**: Use DeviceInfo AdditionalFields to identify Russian locale (LANG/LC_ALL containing "ru_RU") as operator safe-haven indicator
7. **Dead-Drop Pattern**: Apply regex to RemoteUrl in DeviceNetworkEvents and FileName/FolderPath in DeviceFileEvents for Dune-themed repository names: (sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\\d{1,3}

### Key Fixes
- **Remove projections of non-existent fields**: No MD5, ProcessVersionInfoProductVersion, or InitiatingProcessCommandLine in DeviceNetworkEvents
- **Use AdditionalFields JSON parsing** for environment variables and locale detection
- **Leverage available natural fields**: FileName, FolderPath, ProcessCommandLine, RemoteUrl for pattern matching
- **Focus on achievable IOC detection** across the four tables without fabricating field dependencies
- **Apply regex matching** appropriately: FileSize comparison for execution.js (12,150,784 bytes), FolderPath/FileName for suspicious IDE paths, RemoteUrl for C2 and dead-drop patterns, ProcessCommandLine for execution chains

### Expected Output
Corrected KQL query set that:
- Executes without schema errors
- Returns meaningful matches from mock logs matching the provided IOC values
- Covers file hashes, suspicious paths, process execution, network connections, environment variables, and locale attribution
- Maintains campaign-specific signature integrity while respecting available telemetry fields
~~~

### Result

- Candidate 1 executed successfully and returned 3 row(s).
- Candidate 2 executed successfully and returned 2 row(s).
- Candidate 3 executed successfully and returned 1 row(s).
- Candidate 4 executed successfully and returned 3 row(s).
- Candidate 5 executed successfully and returned 1 row(s).
- Candidate 6 executed successfully and returned 3 row(s).
- Candidate 7 executed successfully and returned 2 row(s).
- Candidate 8 executed successfully and returned 1 row(s).
- Candidate 9 executed successfully and returned 0 row(s).

Evaluator feedback:

## Evaluation Summary: Mini Shai-Hulud KQL Detection Queries

**STATUS: SUCCESS** ✓

All nine candidate queries executed successfully against the mock Sentinel logs without schema errors, and queries 1-8 returned meaningful matches aligned with the campaign IOCs. Query 9 returned zero rows, which is expected given the mock data structure.

### Query Performance Analysis

**Best Performer: Query 6 (Network C2 and Registry Detection)**
- **Rows Returned**: 3
- **IOC Coverage**: Excellent
- **Execution**: Flawless
- **Rationale**: Combines three complementary detection approaches:
  1. Direct API endpoint matching (`api.github.com`, `registry.npmjs.org`)
  2. Dead-drop repository pattern recognition (regex matching Dune-themed names)
  3. Captures complete attack chain (RemoteUrl, RemoteIP, RemotePort, Protocol, InitiatingProcessFileName)
- **Impact**: Single query detects both C2 infrastructure and exfiltration channels with minimal false-positive risk

**Secondary High-Value Queries**:
- **Query 1 (File Hash Detection)**: 3 rows; direct IOC matching for all three SHA256 hashes (loader + 2 payloads)
- **Query 4 (Suspicious Process Execution)**: 3 rows; captures all malicious process execution patterns (node setup.mjs, bun run, execution.js)
- **Query 7 (Dead-Drop Repository Pattern)**: 2 rows; focused detection of exfiltration infrastructure

### Coverage Assessment

✅ **File-Based IOCs**: Queries 1-3 comprehensively cover:
  - SHA256 hashes for loader (4066781fa830...) and both payloads (80a3d2877813..., 6f933d00...)
  - Suspicious file paths (.claude/execution.js, .vscode/tasks.json, .claude/settings.json)
  - File size signature for execution.js (12,150,784 bytes)

✅ **Process Behavior**: Query 4 detects:
  - `node .claude/setup.mjs` execution (initiating from npm, VSCode)
  - `node .vscode/setup.mjs` patterns
  - `bun run .claude/execution.js` process chains

✅ **Network IOCs**: Queries 6-7 identify:
  - GitHub API connections (api.github.com)
  - npm registry connections (registry.npmjs.org)
  - Dead-drop repository patterns (sardaukar-sandworm-42, mentat-ornithopter-71)

✅ **Environment Indicators**: Query 5 detects:
  - `__DAEMONIZED` environment variable in AdditionalFields
  - Proper JSON parsing of process environment context

✅ **Locale Attribution**: Query 8 identifies:
  - Russian locale (LANG: ru_RU.UTF-8, LC_ALL: ru_RU.UTF-8)
  - Operator safe-haven indicator via DeviceInfo AdditionalFields

### Key Refinements Successfully Applied

1. **Schema Alignment**: All queries use ONLY available fields from the four tables (DeviceFileEvents, DeviceProcessEvents, DeviceNetworkEvents, DeviceInfo)
2. **Eliminated Non-Existent Fields**: No MD5, ProcessVersionInfoProductVersion, InitiatingProcessCommandLine in network context, or DeviceEvents table references
3. **AdditionalFields JSON Parsing**: Proper use of `has` and `matches regex` operators for environment variable and cryptographic constant detection
4. **Pattern Matching**: Dune-themed dead-drop regex patterns correctly applied to RemoteUrl (network events) and FileName/FolderPath (file events)
5. **Execution Fidelity**: All queries execute without errors and return contextually relevant results

### Mock Log Validation

The mock logs successfully demonstrate:
- **Device 001** (dev-workstation-12): Hash detections, process execution with `__DAEMONIZED`, network C2 to sardaukar-sandworm-42
- **Device 002** (ubuntu-dev-02): Russian locale indicator (LANG/LC_ALL), mentat-ornithopter-71 dead-drop access
- **Device 003** (CI/CD runner): Bun runtime execution, npm registry connections

### Recommended Query Deployment

Deploy as a **query set** covering complementary dimensions:
1. **High-Priority (Immediate)**: Query 1 (file hashes) + Query 6 (network C2) — detects primary attack artifacts and infrastructure
2. **Secondary (Fast-Follow)**: Query 4 (process execution) + Query 5 (environment variables) — confirms malicious behavior and daemonization
3. **Attribution/Forensics**: Query 8 (locale) — identifies operator profile and safe-haven infrastructure
4. **Optional**: Queries 2-3, 7, 9 — granular file path and dead-drop detection for comprehensive coverage

### Notes for Production Deployment

- Adjust `TimeGenerated > ago(7d)` based on incident scope (likely 48-hour window for April 29-30, 2026 campaign)
- Create alerts on Query 1 (exact hash match) and Query 6 (C2 connections) with high fidelity
- Use Query 4 and Query 5 for behavior-based correlation (process + environment variable co-occurrence)
- Baseline Query 8 results to identify systems in Russian locale for supplementary investigation

**Verdict**: All queries meet the detection requirements. Query 6 is the most operationally effective single query. Deploy the full set for maximum campaign coverage across supply chain attack vectors.

KQL generation stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 27315 |
| Output     | 6132 |
| Total      | 33447 |

Evaluation stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 17624 |
| Output     | 1832 |
| Total      | 19456 |

These are the queries we got:

```kql
// Mini Shai-Hulud Supply Chain Attack - File Hash Detection
// Detects known loader and payload SHA256 hashes
DeviceFileEvents
| where TimeGenerated > ago(7d)
| where SHA256 in (
    "4066781fa830224c8bbcc3aa005a396657f9c8f9016f9a64ad44a9d7f5f45e34",
    "80a3d2877813968ef847ae73b5eeeb70b9435254e74d7f07d8cf4057f0a710ac",
    "6f933d00b7d05678eb43c90963a80b8947c4ae6830182f89df31da9f568fea95"
)
| project TimeGenerated, DeviceName, DeviceId, FileName, FolderPath, SHA256, FileSize, InitiatingProcessFileName, InitiatingProcessAccountName
| extend DetectionType = "File Hash IOC"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - Suspicious File Path Detection
// Detects .claude and .vscode directories with execution and setup files
DeviceFileEvents
| where TimeGenerated > ago(7d)
| where (
    (FolderPath contains ".claude" and FileName in ("execution.js", "settings.json")) or
    (FolderPath contains ".vscode" and FileName == "tasks.json")
)
| project TimeGenerated, DeviceName, DeviceId, FileName, FolderPath, FileSize, SHA256, InitiatingProcessFileName, InitiatingProcessAccountName
| extend DetectionType = "Suspicious File Path"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - execution.js File Size Signature
// Detects execution.js with characteristic ~12,150,784 byte size
DeviceFileEvents
| where TimeGenerated > ago(7d)
| where FileName == "execution.js" and FolderPath contains ".claude"
| where FileSize == 12150784 or (FileSize > 12000000 and FileSize < 12300000)
| project TimeGenerated, DeviceName, DeviceId, FileName, FolderPath, FileSize, SHA256, InitiatingProcessFileName, InitiatingProcessAccountName
| extend DetectionType = "Large Execution File"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - Suspicious Process Execution
// Detects process command lines matching node setup patterns and bun execution
DeviceProcessEvents
| where TimeGenerated > ago(7d)
| where ProcessCommandLine matches regex @"node\s+\.(?:claude|vscode)/setup\.mjs|bun\s+run|execution\.js" or
        ProcessCommandLine contains "node .claude/setup.mjs" or
        ProcessCommandLine contains "node .vscode/setup.mjs" or
        ProcessCommandLine contains "bun run"
| project TimeGenerated, DeviceName, DeviceId, FileName, ProcessCommandLine, ProcessId, InitiatingProcessFileName, InitiatingProcessAccountName
| extend DetectionType = "Suspicious Process Execution"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - Environment Variable Indicators in Process Events
// Detects __DAEMONIZED environment variable and cryptographic constants in AdditionalFields
DeviceProcessEvents
| where TimeGenerated > ago(7d)
| where AdditionalFields has "__DAEMONIZED" or
        AdditionalFields has "ctf-scramble-v2" or
        AdditionalFields has "PBKDF2" or
        AdditionalFields matches regex @"ctf-scramble|evasion|daemonized"
| project TimeGenerated, DeviceName, DeviceId, ProcessCommandLine, InitiatingProcessFileName, InitiatingProcessAccountName, AdditionalFields
| extend DetectionType = "Environment Variable IOC"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - Network C2 and Registry Detection
// Detects connections to GitHub API, npm registry, and suspicious domains
DeviceNetworkEvents
| where TimeGenerated > ago(7d)
| where RemoteUrl contains "api.github.com" or
        RemoteUrl contains "registry.npmjs.org" or
        RemoteUrl matches regex @"(sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\d{1,3}"
| project TimeGenerated, DeviceName, DeviceId, InitiatingProcessFileName, RemoteUrl, RemoteIP, RemotePort, Protocol
| extend DetectionType = "Network IOC - C2/Registry"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - Dead-Drop Repository Pattern Detection
// Detects Dune-themed repository names in network URLs and file paths
DeviceNetworkEvents
| where TimeGenerated > ago(7d)
| where RemoteUrl matches regex @"(sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\d{1,3}"
| project TimeGenerated, DeviceName, DeviceId, InitiatingProcessFileName, RemoteUrl, InitiatingProcessAccountName
| extend DetectionType = "Dead-Drop Repository Pattern"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - Russian Locale Attribution
// Identifies operator safe-haven indicator via LANG/LC_ALL environment variables
DeviceInfo
| where TimeGenerated > ago(7d)
| where AdditionalFields has "ru_RU" or
        AdditionalFields matches regex @"LANG.*ru_RU|LC_ALL.*ru_RU"
| project TimeGenerated, DeviceName, DeviceId, OSPlatform, OSVersion, OnboardingStatus, SensorHealthState, AdditionalFields
| extend DetectionType = "Locale Attribution - Russian"
| extend LocaleIndicator = "Russian (ru_RU) - Operator Safe-Haven"
| sort by TimeGenerated desc
```

```kql
// Mini Shai-Hulud - File Path Dead-Drop Detection
// Detects Dune-themed repository patterns in file system paths
DeviceFileEvents
| where TimeGenerated > ago(7d)
| where FolderPath matches regex @"(sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\d{1,3}"
| project TimeGenerated, DeviceName, DeviceId, FileName, FolderPath, InitiatingProcessFileName, InitiatingProcessAccountName
| extend DetectionType = "File Path - Dead-Drop Repository"
| sort by TimeGenerated desc
```

# Links

- [https://www.stepsecurity.io/blog/a-mini-shai-hulud-has-appeared#indicators-of-compromise](https://www.stepsecurity.io/blog/a-mini-shai-hulud-has-appeared#indicators-of-compromise)
- [https://snyk.io/blog/tanstack-npm-packages-compromised/](https://snyk.io/blog/tanstack-npm-packages-compromised/)
- [https://www.upwind.io/feed/mini-shai-hulud-targets-sap-npm-packages-ci-cd-publishing-pipeline-abused-in-supply-chain-attack](https://www.upwind.io/feed/mini-shai-hulud-targets-sap-npm-packages-ci-cd-publishing-pipeline-abused-in-supply-chain-attack)
