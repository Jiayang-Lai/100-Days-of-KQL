# Day 29

Today we are writing query for the recent Axios compromise.

# Note

One of the maintainers fall victim to a highly sophisticated supply chain attack.

# Gen AI Time

## Attempt 1

Microsoft has published a quality [report](https://www.microsoft.com/en-us/security/blog/2026/04/01/mitigating-the-axios-npm-supply-chain-compromise/) on this incident, and this report happened to include an IOC table with a mixture of indicator types. So let's use the table directly within the prompt.

### Prompt

Please find the prompt from this [file](day-29.prompt.md).

### Result

```json
{
  "request": "Generate a KQL query to find Axios compromise IOCs matching C2 domain (sfrclak.com), C2 IP (142.11.206.73), C2 URL (http://sfrclak.com:8000/6202033), file hashes for VBScript dropper, PowerShell payload, batch file, and macOS/Linux binaries, and npm identifiers.",
  "queries": [
    "union\n(DeviceNetworkEvents\n| where RemoteUrl in (\"sfrclak.com\", \"http://sfrclak.com:8000/6202033\")\nor RemoteIP == \"142.11.206.73\"\nor RemotePort == 8000\n| project TimeGenerated, DeviceName, RemoteUrl, RemoteIP, RemotePort, InitiatingProcessFileName, InitiatingProcessCommandLine, Type=\"NetworkIOC\"),\n(DeviceFileEvents\n| where FolderPath in (\"%TEMP%\", \"%PROGRAMDATA%\", \"C:\\\\ProgramData\")\nand FileName in (\"6202033.vbs\", \"6202033.ps1\", \"system.bat\", \"wt.exe\")\nor SHA256 in (\"ed8560c1ac7ceb6983ba995124d5917dc1a00288912387a6389296637d5f815c\",\n\"617b67a8e1210e4fc87c92d1d1da45a2f311c08d26e89b12307cf583c900d101\",\n\"f7d335205b8d7b20208fb3ef93ee6dc817905dc3ae0c10a0b164f4e7d07121cd\",\n\"92ff08773995ebc8d55ec4b8e1a225d0d1e51efa4ef88b8849d0071230c9645a\",\n\"fcb81618bb15edfdedfb638b4c08a2af9cac9ecfa551af135a8402bf980375cf\")\n| project TimeGenerated, DeviceName, FileName, FolderPath, SHA256, InitiatingProcessFileName, InitiatingProcessCommandLine, Type=\"FileIOC\"),\n(DeviceProcessEvents\n| where ProcessCommandLine contains \"packages.npm.org/product0\"\nor ProcessCommandLine contains \"packages.npm.org/product1\"\nor InitiatingProcessCommandLine contains \"packages.npm.org/product0\"\nor InitiatingProcessCommandLine contains \"packages.npm.org/product1\"\nor FolderPath in (\"/Library/Caches\", \"/tmp\")\nand FileName in (\"com.apple.act.mond\", \"ld.py\")\n| project TimeGenerated, DeviceName, FileName, FolderPath, ProcessCommandLine, InitiatingProcessCommandLine, InitiatingProcessFileName, Type=\"ProcessIOC\")\n| sort by TimeGenerated desc"
  ],
  "explanation": "This query hunts for Axios compromise IOCs across network, file, and process events. The query is structured as a union of three sub-queries:\\n\\n1. **DeviceNetworkEvents**: Detects C2 communication attempts by matching the domain sfrclak.com, the URL http://sfrclak.com:8000/6202033, the IP 142.11.206.73, and port 8000 connections.\\n\\n2. **DeviceFileEvents**: Identifies file-based indicators including:\\n   - File names: 6202033.vbs (VBScript dropper), 6202033.ps1 (PowerShell payload), system.bat, and wt.exe\\n   - File paths: %TEMP%, %PROGRAMDATA%, C:\\\\ProgramData\\n   - SHA-256 hashes for all known malicious files (two PowerShell variants, batch file, macOS binary, and Linux loader)\\n\\n3. **DeviceProcessEvents**: Captures npm identifier indicators in command lines (packages.npm.org/product0 for macOS, packages.npm.org/product1 for Windows) and macOS/Linux file creations in /Library/Caches and /tmp directories.\\n\\nAll results are sorted by TimeGenerated in descending order to show the most recent activities first. Each IOC type is labeled for easy identification.",
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
| Input      | 28174 |
| Output     | 2471  |
| Total      | 30645 |

That was probably the highest per run token usage so far (since the model decided to refer to three tables).

Got the query:

```kql
union
(DeviceNetworkEvents
| where RemoteUrl in ("sfrclak.com", "http://sfrclak.com:8000/6202033")
or RemoteIP == "142.11.206.73"
or RemotePort == 8000
| project TimeGenerated, DeviceName, RemoteUrl, RemoteIP, RemotePort, InitiatingProcessFileName, InitiatingProcessCommandLine, Type="NetworkIOC"),
(DeviceFileEvents
| where FolderPath in ("%TEMP%", "%PROGRAMDATA%", "C:\\ProgramData")
and FileName in ("6202033.vbs", "6202033.ps1", "system.bat", "wt.exe")
or SHA256 in ("ed8560c1ac7ceb6983ba995124d5917dc1a00288912387a6389296637d5f815c",
"617b67a8e1210e4fc87c92d1d1da45a2f311c08d26e89b12307cf583c900d101",
"f7d335205b8d7b20208fb3ef93ee6dc817905dc3ae0c10a0b164f4e7d07121cd",
"92ff08773995ebc8d55ec4b8e1a225d0d1e51efa4ef88b8849d0071230c9645a",
"fcb81618bb15edfdedfb638b4c08a2af9cac9ecfa551af135a8402bf980375cf")
| project TimeGenerated, DeviceName, FileName, FolderPath, SHA256, InitiatingProcessFileName, InitiatingProcessCommandLine, Type="FileIOC"),
(DeviceProcessEvents
| where ProcessCommandLine contains "packages.npm.org/product0"
or ProcessCommandLine contains "packages.npm.org/product1"
or InitiatingProcessCommandLine contains "packages.npm.org/product0"
or InitiatingProcessCommandLine contains "packages.npm.org/product1"
or FolderPath in ("/Library/Caches", "/tmp")
and FileName in ("com.apple.act.mond", "ld.py")
| project TimeGenerated, DeviceName, FileName, FolderPath, ProcessCommandLine, InitiatingProcessCommandLine, InitiatingProcessFileName, Type="ProcessIOC")
| sort by TimeGenerated desc
```

To be honest I was slightly surprised when the first attempt worked, the table was a decent challenge for LLM to understand the necessary values. I was also worried that the defanged values would have caused issue, but LLM understood and executed the instructions accurately. In terms of the query itself, it is another solid one. The separation of path and file names ensures wider coverage, which is great for detection.

# Links

- [Mitigating the Axios npm supply chain compromise](https://www.microsoft.com/en-us/security/blog/2026/04/01/mitigating-the-axios-npm-supply-chain-compromise/)
