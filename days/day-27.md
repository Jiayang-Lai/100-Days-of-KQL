# Day 27

Today's query is for identifying CPUID compromise.

# Note

Another DLL sideloading attack.

# Gen AI Time

## Attempt 1

The prompt is quite similar to day 26 since the indicators are same types (hash, filename and URLs), however this time let us try markdown table layout rather than list as we want to evaluate the behaviour of the LLM under different input.

### Prompt

~~~markdown
Generate a KQL query to find CPUID compromise IOCs that match the following criteria:

File and hash indicators:
| SHA1                                     | File Name                   |
| ---------------------------------------- | --------------------------- |
| d0568eaa55f495fd756fa205997ae8d93588d2a2 | cpu-z_2.19-en.zip           |
| 02a53d660332c25af623bbb7df57c2aad1b0b91b | hwinfo_monitor_setup.exe    |
| 9253111b359c610b5f95ef33c2d1c06795ab01e9 | HWMonitorPro_1.57_Setup.exe |
| 2f717a77780b8f6b2d853dc4df5ed2b90a3a349a | hwmonitor-pro_1.57.zip      |
| 7c615ce495ac5be1b64604a7c145347adbcd900c | hwmonitor_1.63.zip          |
| c417c3a4b094646d06a06103639a5c9faabc9ba4 | hwmonitor_1.63.zip          |
| 8351a43a0c0455e4b0793d841fe12625f072f9b4 | PerfMonitor2_Setup.exe      |
| 6a71656c289201f742787f48398056fcd2aa7274 | perfmonitor-2_2.04.zip      |
| c65e515b9c9655c651c939b94574cf39b40a8be2 | CRYPTBASE.dll.bin           |
| 3041a4e2bc5ccefbfd2222a9e23614fb79d6db63 | CRYPTBASE.dll               |
| 4e3195399a9135247e55781ad13226c6b0e86c0d | CRYPTBASE.dll               |
| 4597f546a622ae55e0775cbcc416b3f1dfd096ce | CRYPTBASE.dll               |
| a06955d253711385eaa6f5af76fa9fa47bdeb1e9 | CRYPTBASE.dll               |
| 6b49823483889bc1ad152a1be52d1385c4e0affb | CRYPTBASE.dll               |
| 3041a4e2bc5ccefbfd2222a9e23614fb79d6db63 | CRYPTBASE.dll               |
| c65e515b9c9655c651c939b94574cf39b40a8be2 | CRYPTBASE.dll               |
| 4f3d8c47239bd1585488ce431d931457f101104c | CRYPTBASE.dll               |
| ba19e03ca03785e89010672d7e273ac343e4699a | CRYPTBASE.dll               |
| e2464454017cd02a8bc6744596c384cf91cdd67e | CRYPTBASE.dll               |

Network indicators:
- welcome.supp0v3.com
~~~

### Result

```json
{
  "request": "Generate a KQL query to find CPUID compromise IOCs that match file/hash indicators and network indicators for known malware campaigns",
  "queries": [
    "// Query 1: Find file and hash indicators related to CPUID compromise\nlet suspiciousHashes = dynamic([\n    \"d0568eaa55f495fd756fa205997ae8d93588d2a2\",\n    \"02a53d660332c25af623bbb7df57c2aad1b0b91b\",\n    \"9253111b359c610b5f95ef33c2d1c06795ab01e9\",\n    \"2f717a77780b8f6b2d853dc4df5ed2b90a3a349a\",\n    \"7c615ce495ac5be1b64604a7c145347adbcd900c\",\n    \"c417c3a4b094646d06a06103639a5c9faabc9ba4\",\n    \"8351a43a0c0455e4b0793d841fe12625f072f9b4\",\n    \"6a71656c289201f742787f48398056fcd2aa7274\",\n    \"c65e515b9c9655c651c939b94574cf39b40a8be2\",\n    \"3041a4e2bc5ccefbfd2222a9e23614fb79d6db63\",\n    \"4e3195399a9135247e55781ad13226c6b0e86c0d\",\n    \"4597f546a622ae55e0775cbcc416b3f1dfd096ce\",\n    \"a06955d253711385eaa6f5af76fa9fa47bdeb1e9\",\n    \"6b49823483889bc1ad152a1be52d1385c4e0affb\",\n    \"4f3d8c47239bd1585488ce431d931457f101104c\",\n    \"ba19e03ca03785e89010672d7e273ac343e4699a\",\n    \"e2464454017cd02a8bc6744596c384cf91cdd67e\"\n]);\nlet suspiciousFileNames = dynamic([\n    \"cpu-z_2.19-en.zip\",\n    \"hwinfo_monitor_setup.exe\",\n    \"HWMonitorPro_1.57_Setup.exe\",\n    \"hwmonitor-pro_1.57.zip\",\n    \"hwmonitor_1.63.zip\",\n    \"PerfMonitor2_Setup.exe\",\n    \"perfmonitor-2_2.04.zip\",\n    \"CRYPTBASE.dll.bin\",\n    \"CRYPTBASE.dll\"\n]);\nDeviceFileEvents\n| where SHA1 in (suspiciousHashes) or FileName in (suspiciousFileNames)\n| project TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, SHA1, MD5, SHA256, FileSize, ActionType, InitiatingProcessFileName, InitiatingProcessSHA1, InitiatingProcessCommandLine",
    "// Query 2: Find network connections to known CPUID malware C2 domain\nlet suspiciousDomains = dynamic([\n    \"welcome.supp0v3.com\"\n]);\nDeviceNetworkEvents\n| where RemoteUrl has_any (suspiciousDomains) or RemoteUrl matches regex @\"(?i)welcome\\.supp0v3\\.com\"\n| project TimeGenerated, DeviceId, DeviceName, RemoteUrl, RemoteIP, RemotePort, LocalIP, LocalPort, InitiatingProcessFileName, InitiatingProcessSHA1, InitiatingProcessCommandLine, Protocol, ActionType",
    "// Query 3: Comprehensive correlation - File execution followed by network communication\nlet suspiciousHashes = dynamic([\n    \"d0568eaa55f495fd756fa205997ae8d93588d2a2\",\n    \"02a53d660332c25af623bbb7df57c2aad1b0b91b\",\n    \"9253111b359c610b5f95ef33c2d1c06795ab01e9\",\n    \"2f717a77780b8f6b2d853dc4df5ed2b90a3a349a\",\n    \"7c615ce495ac5be1b64604a7c145347adbcd900c\",\n    \"c417c3a4b094646d06a06103639a5c9faabc9ba4\",\n    \"8351a43a0c0455e4b0793d841fe12625f072f9b4\",\n    \"6a71656c289201f742787f48398056fcd2aa7274\",\n    \"c65e515b9c9655c651c939b94574cf39b40a8be2\",\n    \"3041a4e2bc5ccefbfd2222a9e23614fb79d6db63\",\n    \"4e3195399a9135247e55781ad13226c6b0e86c0d\",\n    \"4597f546a622ae55e0775cbcc416b3f1dfd096ce\",\n    \"a06955d253711385eaa6f5af76fa9fa47bdeb1e9\",\n    \"6b49823483889bc1ad152a1be52d1385c4e0affb\",\n    \"4f3d8c47239bd1585488ce431d931457f101104c\",\n    \"ba19e03ca03785e89010672d7e273ac343e4699a\",\n    \"e2464454017cd02a8bc6744596c384cf91cdd67e\"\n]);\nlet suspiciousDomains = dynamic([\n    \"welcome.supp0v3.com\"\n]);\nlet malwareFiles = DeviceFileEvents\n| where SHA1 in (suspiciousHashes)\n| project FileCreationTime = TimeGenerated, DeviceId, DeviceName, SHA1, FileName, InitiatingProcessId;\nlet malwareNetworkActivity = DeviceNetworkEvents\n| where RemoteUrl has_any (suspiciousDomains)\n| project NetworkEventTime = TimeGenerated, DeviceId, RemoteUrl, RemoteIP, InitiatingProcessId, InitiatingProcessFileName;\nmalwareFiles\n| join kind=inner (malwareNetworkActivity) on DeviceId, InitiatingProcessId\n| project FileCreationTime, NetworkEventTime, DeviceId, DeviceName, FileName, SHA1, RemoteUrl, RemoteIP, InitiatingProcessFileName\n| order by FileCreationTime desc"
  ],
  "explanation": "These three KQL queries help detect CPUID compromise IOCs across your Microsoft Sentinel environment:\\n\\n**Query 1 (File Hash & Filename Detection)**: Searches DeviceFileEvents for files matching the known malicious SHA1 hashes or filenames associated with the CPUID campaign. This includes tools like CPU-Z, HWInfo, HWMonitor, and PerfMonitor variants, as well as suspicious CRYPTBASE.dll files. Results include full file details and the process that created/modified them.\\n\\n**Query 2 (Network C2 Detection)**: Searches DeviceNetworkEvents for connections to the known command-and-control domain \\\"welcome.supp0v3.com\\\". This captures any network communication attempts to this malicious domain, including the initiating process details and connection parameters.\\n\\n**Query 3 (Correlation Analysis)**: Performs an inner join between malicious file events and network connections on the same device and process ID. This identifies cases where suspicious files were created and subsequently made network connections to the C2 domain, indicating active compromise activity.\\n\\nAll queries return comprehensive details including timestamps, device information, file hashes, process details, and network indicators for investigation and response purposes.",
  "tables_used": [
    "DeviceFileEvents",
    "DeviceNetworkEvents"
  ]
}
```

Stats:

| Token Type | Value |
| ---------- | ----- |
| Input      | 10320 |
| Output     | 2202  |
| Total      | 12522 |

These are the queries we got:

```kql
// Query 1: Find file and hash indicators related to CPUID compromise
let suspiciousHashes = dynamic([
    "d0568eaa55f495fd756fa205997ae8d93588d2a2",
    "02a53d660332c25af623bbb7df57c2aad1b0b91b",
    "9253111b359c610b5f95ef33c2d1c06795ab01e9",
    "2f717a77780b8f6b2d853dc4df5ed2b90a3a349a",
    "7c615ce495ac5be1b64604a7c145347adbcd900c",
    "c417c3a4b094646d06a06103639a5c9faabc9ba4",
    "8351a43a0c0455e4b0793d841fe12625f072f9b4",
    "6a71656c289201f742787f48398056fcd2aa7274",
    "c65e515b9c9655c651c939b94574cf39b40a8be2",
    "3041a4e2bc5ccefbfd2222a9e23614fb79d6db63",
    "4e3195399a9135247e55781ad13226c6b0e86c0d",
    "4597f546a622ae55e0775cbcc416b3f1dfd096ce",
    "a06955d253711385eaa6f5af76fa9fa47bdeb1e9",
    "6b49823483889bc1ad152a1be52d1385c4e0affb",
    "4f3d8c47239bd1585488ce431d931457f101104c",
    "ba19e03ca03785e89010672d7e273ac343e4699a",
    "e2464454017cd02a8bc6744596c384cf91cdd67e"
]);
let suspiciousFileNames = dynamic([
    "cpu-z_2.19-en.zip",
    "hwinfo_monitor_setup.exe",
    "HWMonitorPro_1.57_Setup.exe",
    "hwmonitor-pro_1.57.zip",
    "hwmonitor_1.63.zip",
    "PerfMonitor2_Setup.exe",
    "perfmonitor-2_2.04.zip",
    "CRYPTBASE.dll.bin",
    "CRYPTBASE.dll"
]);
DeviceFileEvents
| where SHA1 in (suspiciousHashes) or FileName in (suspiciousFileNames)
| project TimeGenerated, DeviceId, DeviceName, FileName, FolderPath, SHA1, MD5, SHA256, FileSize, ActionType, InitiatingProcessFileName, InitiatingProcessSHA1, InitiatingProcessCommandLine
```

```kql
// Query 2: Find network connections to known CPUID malware C2 domain
let suspiciousDomains = dynamic([
    "welcome.supp0v3.com"
]);
DeviceNetworkEvents
| where RemoteUrl has_any (suspiciousDomains) or RemoteUrl matches regex @"(?i)welcome\.supp0v3\.com"
| project TimeGenerated, DeviceId, DeviceName, RemoteUrl, RemoteIP, RemotePort, LocalIP, LocalPort, InitiatingProcessFileName, InitiatingProcessSHA1, InitiatingProcessCommandLine, Protocol, ActionType
```

```kql
// Query 3: Comprehensive correlation - File execution followed by network communication
let suspiciousHashes = dynamic([
    "d0568eaa55f495fd756fa205997ae8d93588d2a2",
    "02a53d660332c25af623bbb7df57c2aad1b0b91b",
    "9253111b359c610b5f95ef33c2d1c06795ab01e9",
    "2f717a77780b8f6b2d853dc4df5ed2b90a3a349a",
    "7c615ce495ac5be1b64604a7c145347adbcd900c",
    "c417c3a4b094646d06a06103639a5c9faabc9ba4",
    "8351a43a0c0455e4b0793d841fe12625f072f9b4",
    "6a71656c289201f742787f48398056fcd2aa7274",
    "c65e515b9c9655c651c939b94574cf39b40a8be2",
    "3041a4e2bc5ccefbfd2222a9e23614fb79d6db63",
    "4e3195399a9135247e55781ad13226c6b0e86c0d",
    "4597f546a622ae55e0775cbcc416b3f1dfd096ce",
    "a06955d253711385eaa6f5af76fa9fa47bdeb1e9",
    "6b49823483889bc1ad152a1be52d1385c4e0affb",
    "4f3d8c47239bd1585488ce431d931457f101104c",
    "ba19e03ca03785e89010672d7e273ac343e4699a",
    "e2464454017cd02a8bc6744596c384cf91cdd67e"
]);
let suspiciousDomains = dynamic([
    "welcome.supp0v3.com"
]);
let malwareFiles = DeviceFileEvents
| where SHA1 in (suspiciousHashes)
| project FileCreationTime = TimeGenerated, DeviceId, DeviceName, SHA1, FileName, InitiatingProcessId;
let malwareNetworkActivity = DeviceNetworkEvents
| where RemoteUrl has_any (suspiciousDomains)
| project NetworkEventTime = TimeGenerated, DeviceId, RemoteUrl, RemoteIP, InitiatingProcessId, InitiatingProcessFileName;
malwareFiles
| join kind=inner (malwareNetworkActivity) on DeviceId, InitiatingProcessId
| project FileCreationTime, NetworkEventTime, DeviceId, DeviceName, FileName, SHA1, RemoteUrl, RemoteIP, InitiatingProcessFileName
| order by FileCreationTime desc
```

All queries work, Markdown table is piece of cake to LLM.

![Happy Cat](.pics/happy-cat.gif)

Realistically we only want a single query, previous change to the prompt is likely the reason why LLM started spitting multiple ones (to be honest the Pydantic class for structured output defines the query bit as a list so could another contributing factor). Might change the prompt and the Pydantic class next time.

# Links
- [CPU-Z / HWMonitor watering hole infection – a copy-pasted attack](https://securelist.com/tr/cpu-z/119365/): worth noting that the first hash under `Hashes of malicious DLLs` is invalide as it is one character short of SHA1 length.
- [Security PSA: Popular Tools CPU-Z and HWMonitor Were Briefly Compromised](https://www.techpowerup.com/348138/security-psa-popular-tools-cpu-z-and-hwmonitor-were-briefly-compromised)
- [Monitoring the Monitor: How CPUID's HWMonitor Supply Chain Was Hijacked to Deploy STX RAT](https://www.cyderes.com/howler-cell/how-cpuids-hwmonitor-supply-chain-was-hijacked-to-deploy-stx-rat)
- [CPUID hacked to deliver malware via CPU-Z, HWMonitor downloads](https://www.bleepingcomputer.com/news/security/supply-chain-attack-at-cpuid-pushes-malware-with-cpu-z-hwmonitor/)
