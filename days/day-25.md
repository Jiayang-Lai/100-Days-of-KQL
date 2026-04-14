# Day 25

Today we are writing a KQL query to identify indicator of compromise related to the Trivy, a security scanner used widely.

# Note

The adversary exploited a misconfiguration of GitHub action templates (pull_request_target).

# Gen AI Time

## Attempt 1

### Prompt

```markdown
Generate a KQL query related to Trivy compromise to identify IOC that matches the following criteria:

Network indicators:

IP addresses:
- 45.148.10.212

Domains:
- scan.aquasecurtiy.org
- tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io
- plug-tab-protective-relay.trycloudflare.com

Hash indicators:

SHA256 hashes:
- 0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349

```

### Result

```json
{
  "request": "Generate a KQL query to identify IOCs related to Trivy compromise with the following indicators: IP address 45.148.10.212, domains (scan.aquasecurtiy.org, tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io, plug-tab-protective-relay.trycloudflare.com), and SHA256 hash 0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349",
  "queries": [
    "// Trivy Compromise - Multi-IOC Detection Query\n// Detects network connections and file hashes associated with Trivy malware compromise\n// Covers: IP addresses, domains, and SHA256 hashes\n\nlet SuspiciousIP = dynamic([\"45.148.10.212\"]);\nlet SuspiciousDomains = dynamic([\n    \"scan.aquasecurtiy.org\",\n    \"tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io\",\n    \"plug-tab-protective-relay.trycloudflare.com\"\n]);\nlet SuspiciousSHA256 = dynamic([\"0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349\"]);\n\n// Detect network connections to malicious IP\n(\nDeviceNetworkEvents\n| where RemoteIP in (SuspiciousIP)\n| project TimeGenerated, DeviceId, DeviceName, RemoteIP, RemotePort, Protocol, \n    InitiatingProcessFileName, InitiatingProcessId, InitiatingProcessSHA256,\n    InitiatingProcessCommandLine, ActionType\n| extend IOCType = \"IP Address\", IOCValue = RemoteIP\n)\n// Union with domain-based network connections\nunion\n(\nDeviceNetworkEvents\n| where RemoteUrl has_any (SuspiciousDomains)\n| project TimeGenerated, DeviceId, DeviceName, RemoteUrl, RemotePort, Protocol,\n    InitiatingProcessFileName, InitiatingProcessId, InitiatingProcessSHA256,\n    InitiatingProcessCommandLine, ActionType\n| extend IOCType = \"Domain\", IOCValue = RemoteUrl\n)\n// Union with file hash detections\nunion\n(\nDeviceFileEvents\n| where SHA256 in (SuspiciousSHA256)\n| project TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, SHA256,\n    FileSize, ActionType, InitiatingProcessFileName, InitiatingProcessId\n| extend IOCType = \"SHA256 Hash\", IOCValue = SHA256\n)\n// Union with process hash detections\nunion\n(\nDeviceNetworkEvents\n| where InitiatingProcessSHA256 in (SuspiciousSHA256)\n| project TimeGenerated, DeviceId, DeviceName, RemoteIP, RemoteUrl, RemotePort,\n    InitiatingProcessFileName, InitiatingProcessSHA256, InitiatingProcessCommandLine,\n    ActionType\n| extend IOCType = \"Process SHA256 Hash\", IOCValue = InitiatingProcessSHA256\n)\n| sort by TimeGenerated desc"
  ],
  "explanation": "This comprehensive KQL query detects Trivy compromise indicators across multiple dimensions:\\n\\n1. **IP-based Detection**: Monitors DeviceNetworkEvents for connections to the malicious IP address 45.148.10.212\\n2. **Domain-based Detection**: Searches RemoteUrl field for connections to the three identified malicious domains\\n3. **File Hash Detection**: Queries DeviceFileEvents for files matching the suspicious SHA256 hash\\n4. **Process Hash Detection**: Identifies processes with matching SHA256 hashes initiating network connections\\n\\nKey features:\\n- Uses dynamic arrays for easy IOC management\\n- Enriches results with IOCType and IOCValue columns for clarity\\n- Combines multiple detection methods using union operators\\n- Includes process and network context (command line, process name, file paths)\\n- Sorts results by timestamp in descending order for latest incidents first\\n- Captures both suspicious files and the processes that spawned them\\n\\nThe query will surface any endpoint that has:\\n- Connected to the attacker's infrastructure\\n- Downloaded or executed files with the known malicious hash\\n- Initiated suspicious processes with the known hash",
  "tables_used": [
    "DeviceNetworkEvents",
    "DeviceFileEvents"
  ]
}
```

Stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 20570 |
| Output     | 2529  |
| Total      | 23099 |

From the return above we get this KQL query:

```kql
// Trivy Compromise - Multi-IOC Detection Query
// Detects network connections and file hashes associated with Trivy malware compromise
// Covers: IP addresses, domains, and SHA256 hashes

let SuspiciousIP = dynamic(["45.148.10.212"]);
let SuspiciousDomains = dynamic([
    "scan.aquasecurtiy.org",
    "tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io",
    "plug-tab-protective-relay.trycloudflare.com"
]);
let SuspiciousSHA256 = dynamic(["0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349"]);

// Detect network connections to malicious IP
(
DeviceNetworkEvents
| where RemoteIP in (SuspiciousIP)
| project TimeGenerated, DeviceId, DeviceName, RemoteIP, RemotePort, Protocol, 
    InitiatingProcessFileName, InitiatingProcessId, InitiatingProcessSHA256,
    InitiatingProcessCommandLine, ActionType
| extend IOCType = "IP Address", IOCValue = RemoteIP
)
// Union with domain-based network connections
union
(
DeviceNetworkEvents
| where RemoteUrl has_any (SuspiciousDomains)
| project TimeGenerated, DeviceId, DeviceName, RemoteUrl, RemotePort, Protocol,
    InitiatingProcessFileName, InitiatingProcessId, InitiatingProcessSHA256,
    InitiatingProcessCommandLine, ActionType
| extend IOCType = "Domain", IOCValue = RemoteUrl
)
// Union with file hash detections
union
(
DeviceFileEvents
| where SHA256 in (SuspiciousSHA256)
| project TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, SHA256,
    FileSize, ActionType, InitiatingProcessFileName, InitiatingProcessId
| extend IOCType = "SHA256 Hash", IOCValue = SHA256
)
// Union with process hash detections
union
(
DeviceNetworkEvents
| where InitiatingProcessSHA256 in (SuspiciousSHA256)
| project TimeGenerated, DeviceId, DeviceName, RemoteIP, RemoteUrl, RemotePort,
    InitiatingProcessFileName, InitiatingProcessSHA256, InitiatingProcessCommandLine,
    ActionType
| extend IOCType = "Process SHA256 Hash", IOCValue = InitiatingProcessSHA256
)
| sort by TimeGenerated desc
```

The basic logic is correct. However, the usage is wrong as KQL's union should be declared at the start like this:

```kql
// Using union isfuzzy=true to access non-existing view:                                     
let View_1 = view () { print x=1 };
let View_2 = view () { print x=1 };
let OtherView_1 = view () { print x=1 };
union isfuzzy=true
(View_1 | where x > 0), 
(View_2 | where x > 0),
(View_3 | where x > 0)
| count 
```

## Attempt 2

Let us provide an example of union operator this time.

### Prompt

~~~markdown
Generate a KQL query related to Trivy compromise to identify IOC that matches the following criteria:

Network indicators:

IP addresses:
- 45.148.10.212

Domains:
- scan.aquasecurtiy.org
- tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io
- plug-tab-protective-relay.trycloudflare.com

Hash indicators:

SHA256 hashes:
- 0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349

Here is an example of how to use union operator to combine multiple queries for different indicators:

```kql
// Using union isfuzzy=true to access non-existing view:                                     
let View_1 = view () { print x=1 };
let View_2 = view () { print x=1 };
union isfuzzy=true
(View_1 | where x > 0), 
(View_2 | where x > 0)
```
~~~

### Result

```json
{
  "request": "Generate a KQL query related to Trivy compromise to identify IOC (Indicators of Compromise) that matches network indicators (IP addresses and domains) and hash indicators (SHA256 hashes)",
  "queries": [
    "// Trivy Compromise IOC Detection\n// This query searches for indicators of compromise related to Trivy vulnerability scanner compromise\n// Identifies network connections and file activity matching known malicious IOCs\n\nlet malicious_ips = dynamic([\n    \"45.148.10.212\"\n]);\n\nlet malicious_domains = dynamic([\n    \"scan.aquasecurtiy.org\",\n    \"tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io\",\n    \"plug-tab-protective-relay.trycloudflare.com\"\n]);\n\nlet malicious_sha256 = dynamic([\n    \"0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349\"\n]);\n\n// Query 1: Network connections to malicious IPs and domains\nlet network_indicators = \n    DeviceNetworkEvents\n    | where TimeGenerated > ago(30d)\n    | where RemoteIP in (malicious_ips) \n        or RemoteUrl has_any (malicious_domains)\n    | project \n        TimeGenerated,\n        DeviceName,\n        DeviceId,\n        InitiatingProcessFileName,\n        InitiatingProcessId,\n        InitiatingProcessCommandLine,\n        RemoteIP,\n        RemoteUrl,\n        RemotePort,\n        ActionType,\n        IndicatorType = \"Network Connection\",\n        MatchedIOC = iff(RemoteIP in (malicious_ips), RemoteIP, RemoteUrl);\n\n// Query 2: Files with malicious SHA256 hashes\nlet file_indicators = \n    DeviceFileEvents\n    | where TimeGenerated > ago(30d)\n    | where SHA256 in (malicious_sha256)\n    | project \n        TimeGenerated,\n        DeviceName,\n        DeviceId,\n        FileName,\n        FolderPath,\n        InitiatingProcessFileName,\n        InitiatingProcessId,\n        InitiatingProcessCommandLine,\n        SHA256,\n        ActionType,\n        IndicatorType = \"File Hash\",\n        MatchedIOC = SHA256;\n\n// Query 3: Processes with malicious SHA256 hashes\nlet process_indicators = \n    DeviceProcessEvents\n    | where TimeGenerated > ago(30d)\n    | where SHA256 in (malicious_sha256) or InitiatingProcessSHA256 in (malicious_sha256)\n    | project \n        TimeGenerated,\n        DeviceName,\n        DeviceId,\n        FileName,\n        FolderPath,\n        ProcessCommandLine,\n        SHA256,\n        ActionType,\n        IndicatorType = \"Process Hash\",\n        MatchedIOC = iff(SHA256 in (malicious_sha256), SHA256, InitiatingProcessSHA256);\n\n// Combine all indicators using union\nunion isfuzzy=true\n    (network_indicators),\n    (file_indicators),\n    (process_indicators)\n| sort by TimeGenerated desc\n| summarize \n    EventCount = count(),\n    FirstSeen = min(TimeGenerated),\n    LastSeen = max(TimeGenerated),\n    AffectedDevices = dcount(DeviceName)\n    by DeviceName, MatchedIOC, IndicatorType"
  ],
  "explanation": "This KQL query detects Trivy compromise indicators by:\\n\\n1. **Network Indicators Detection**:\\n   - Searches DeviceNetworkEvents for connections to the malicious IP address (45.148.10.212)\\n   - Searches for connections to known malicious domains (scan.aquasecurtiy.org, tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io, plug-tab-protective-relay.trycloudflare.com)\\n   - Captures process details and connection metadata\\n\\n2. **File Hash Detection**:\\n   - Searches DeviceFileEvents for files matching the malicious SHA256 hash\\n   - Captures file creation/modification events and associated process information\\n\\n3. **Process Hash Detection**:\\n   - Searches DeviceProcessEvents for process executions matching the malicious SHA256 hash\\n   - Captures process creation details and parent process information\\n\\n4. **Union Operation**:\\n   - Combines all three indicator types using union with isfuzzy=true to handle variations\\n   - Aggregates results by device, IOC, and indicator type\\n   - Provides summary statistics including event count, timeframe, and affected devices\\n\\nThe 30-day lookback window can be adjusted based on your investigation scope.",
  "tables_used": [
    "DeviceNetworkEvents",
    "DeviceFileEvents",
    "DeviceProcessEvents"
  ]
}
```

Stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 11479 |
| Output     | 1495  |
| Total      | 12974 |

From the return above we get this KQL query:

```kql
// Trivy Compromise IOC Detection
// This query searches for indicators of compromise related to Trivy vulnerability scanner compromise
// Identifies network connections and file activity matching known malicious IOCs

let malicious_ips = dynamic([
    "45.148.10.212"
]);

let malicious_domains = dynamic([
    "scan.aquasecurtiy.org",
    "tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io",
    "plug-tab-protective-relay.trycloudflare.com"
]);

let malicious_sha256 = dynamic([
    "0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349"
]);

// Query 1: Network connections to malicious IPs and domains
let network_indicators = 
    DeviceNetworkEvents
    | where TimeGenerated > ago(30d)
    | where RemoteIP in (malicious_ips) 
        or RemoteUrl has_any (malicious_domains)
    | project 
        TimeGenerated,
        DeviceName,
        DeviceId,
        InitiatingProcessFileName,
        InitiatingProcessId,
        InitiatingProcessCommandLine,
        RemoteIP,
        RemoteUrl,
        RemotePort,
        ActionType,
        IndicatorType = "Network Connection",
        MatchedIOC = iff(RemoteIP in (malicious_ips), RemoteIP, RemoteUrl);

// Query 2: Files with malicious SHA256 hashes
let file_indicators = 
    DeviceFileEvents
    | where TimeGenerated > ago(30d)
    | where SHA256 in (malicious_sha256)
    | project 
        TimeGenerated,
        DeviceName,
        DeviceId,
        FileName,
        FolderPath,
        InitiatingProcessFileName,
        InitiatingProcessId,
        InitiatingProcessCommandLine,
        SHA256,
        ActionType,
        IndicatorType = "File Hash",
        MatchedIOC = SHA256;

// Query 3: Processes with malicious SHA256 hashes
let process_indicators = 
    DeviceProcessEvents
    | where TimeGenerated > ago(30d)
    | where SHA256 in (malicious_sha256) or InitiatingProcessSHA256 in (malicious_sha256)
    | project 
        TimeGenerated,
        DeviceName,
        DeviceId,
        FileName,
        FolderPath,
        ProcessCommandLine,
        SHA256,
        ActionType,
        IndicatorType = "Process Hash",
        MatchedIOC = iff(SHA256 in (malicious_sha256), SHA256, InitiatingProcessSHA256);

// Combine all indicators using union
union isfuzzy=true
    (network_indicators),
    (file_indicators),
    (process_indicators)
| sort by TimeGenerated desc
| summarize 
    EventCount = count(),
    FirstSeen = min(TimeGenerated),
    LastSeen = max(TimeGenerated),
    AffectedDevices = dcount(DeviceName)
    by DeviceName, MatchedIOC, IndicatorType
```

It just works, happy days. Since the sample logs I got don't have matching values, I just replaced some IOC values with existing ones from the logs to test it the query return as expected, and it worked perfectly.

Except there is one thing worth noting: the AI generated KQL query somehow doesn't work with my environment, I suspect it's due to the spaces as when I removed them the query worked.

### Bonus

To achieve end-to-end flow, I added a requirement to not include empty line in the prompt like this:

~~~markdown
Generate a KQL query related to Trivy compromise to identify IOC that matches the following criteria:

Network indicators:

IP addresses:
- 45.148.10.212

Domains:
- scan.aquasecurtiy.org
- tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io
- plug-tab-protective-relay.trycloudflare.com

Hash indicators:

SHA256 hashes:
- 0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349

Here is an example of how to use union operator to combine multiple queries for different indicators:

```kql
// Using union isfuzzy=true to access non-existing view:                                     
let View_1 = view () { print x=1 };
let View_2 = view () { print x=1 };
union isfuzzy=true
(View_1 | where x > 0), 
(View_2 | where x > 0)
```

The query should not include empty lines.
~~~

Then ran the script and got this:

```json
{
  "request": "Generate a KQL query for Trivy compromise detection using network indicators (IP addresses and domains) and file hash indicators",
  "queries": [
    "// Trivy Compromise IOC Detection\n// Detects network connections to malicious IPs and domains, and file execution with known malicious hashes\nlet MaliciousIPs = dynamic(['45.148.10.212']);\nlet MaliciousDomains = dynamic(['scan.aquasecurtiy.org', 'tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io', 'plug-tab-protective-relay.trycloudflare.com']);\nlet MaliciousSHA256 = dynamic(['0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349']);\nunion isfuzzy=true\n(DeviceNetworkEvents\n| where RemoteIP in (MaliciousIPs)\n| project TimeGenerated, DeviceName, RemoteIP, RemotePort, RemoteUrl, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType, Protocol\n| extend IOCType = 'Malicious IP Address'),\n(DeviceNetworkEvents\n| where RemoteUrl has_any (MaliciousDomains)\n| project TimeGenerated, DeviceName, RemoteIP, RemotePort, RemoteUrl, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType, Protocol\n| extend IOCType = 'Malicious Domain'),\n(DeviceFileEvents\n| where SHA256 in (MaliciousSHA256) or InitiatingProcessSHA256 in (MaliciousSHA256)\n| project TimeGenerated, DeviceName, FileName, FolderPath, SHA256, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType\n| extend IOCType = 'Malicious File Hash'),\n(DeviceProcessEvents\n| where SHA256 in (MaliciousSHA256) or InitiatingProcessSHA256 in (MaliciousSHA256)\n| project TimeGenerated, DeviceName, FileName, FolderPath, SHA256, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType\n| extend IOCType = 'Malicious Process Hash')\n| sort by TimeGenerated desc"
  ],
  "explanation": "This KQL query detects Trivy compromise indicators across multiple data sources:\\n\\n1. **Network Indicators - IP Addresses**: Matches connections to the malicious IP 45.148.10.212 using DeviceNetworkEvents RemoteIP field\\n\\n2. **Network Indicators - Domains**: Detects DNS resolutions or connections to any of the three malicious domains (scan.aquasecurtiy.org, tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io, plug-tab-protective-relay.trycloudflare.com) using RemoteUrl field with has_any operator for flexible domain matching\\n\\n3. **Hash Indicators - SHA256**: Searches for the malicious SHA256 hash (0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349) in both DeviceFileEvents and DeviceProcessEvents tables, checking both executed file hashes and initiating process hashes\\n\\n4. **Union Operator**: Uses isfuzzy=true to combine all four detection paths (IP, Domain, File Hash, Process Hash) into a single result set\\n\\n5. **Output**: Returns relevant context fields (timestamp, device name, process details, file information, action type) and tags each match with its IOC type for quick identification. Results are sorted by timestamp in descending order to show most recent detections first.",
  "tables_used": [
    "DeviceNetworkEvents",
    "DeviceFileEvents",
    "DeviceProcessEvents"
  ]
}
```

Stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 11506 |
| Output     | 1202  |
| Total      | 12708 |

Here is the query we get:

```kql
// Trivy Compromise IOC Detection
// Detects network connections to malicious IPs and domains, and file execution with known malicious hashes
let MaliciousIPs = dynamic(['45.148.10.212']);
let MaliciousDomains = dynamic(['scan.aquasecurtiy.org', 'tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io', 'plug-tab-protective-relay.trycloudflare.com']);
let MaliciousSHA256 = dynamic(['0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349']);
union isfuzzy=true
(DeviceNetworkEvents
| where RemoteIP in (MaliciousIPs)
| project TimeGenerated, DeviceName, RemoteIP, RemotePort, RemoteUrl, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType, Protocol
| extend IOCType = 'Malicious IP Address'),
(DeviceNetworkEvents
| where RemoteUrl has_any (MaliciousDomains)
| project TimeGenerated, DeviceName, RemoteIP, RemotePort, RemoteUrl, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType, Protocol
| extend IOCType = 'Malicious Domain'),
(DeviceFileEvents
| where SHA256 in (MaliciousSHA256) or InitiatingProcessSHA256 in (MaliciousSHA256)
| project TimeGenerated, DeviceName, FileName, FolderPath, SHA256, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType
| extend IOCType = 'Malicious File Hash'),
(DeviceProcessEvents
| where SHA256 in (MaliciousSHA256) or InitiatingProcessSHA256 in (MaliciousSHA256)
| project TimeGenerated, DeviceName, FileName, FolderPath, SHA256, InitiatingProcessFileName, InitiatingProcessCommandLine, InitiatingProcessSHA256, ActionType
| extend IOCType = 'Malicious Process Hash')
| sort by TimeGenerated desc
```

To no surprise this query also works, and it doesn't require manual intervention at all. Interestingly Haiku decided to use inline manipulation rather than declaring variables this time, both of which are quite common approaches.

# Links

- [Trivy GitHub Actions Supply Chain Compromise (Snyk)](https://snyk.io/articles/trivy-github-actions-supply-chain-compromise/)
- [Trivy Compromised: Everything You Need to Know about the Latest Supply Chain Attack (Wiz)](https://www.wiz.io/blog/trivy-compromised-teampcp-supply-chain-attack)
- [Update: Ongoing Investigation and Continued Remediation (Aqua)](https://www.aquasec.com/blog/trivy-supply-chain-attack-what-you-need-to-know/)
- [From Scanner to Stealer: Inside the trivy-action Supply Chain Compromise (CrowdStrike)](https://www.crowdstrike.com/en-us/blog/from-scanner-to-stealer-inside-the-trivy-action-supply-chain-compromise/)
