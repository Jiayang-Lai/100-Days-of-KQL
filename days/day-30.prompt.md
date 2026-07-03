# KQL Detection Prompt: The Mini Shai-Hulud Campaign (April 2026)

Generate a comprehensive KQL query or set of KQL detection rules to identify artifacts and behaviors associated with the Mini Shai-Hulud supply chain attack campaign.

## Campaign Overview
- **Campaign Name:** The Mini Shai-Hulud Campaign (Third Wave)
- **Timeframe:** April 29–30, 2026
- **Threat Actor:** TeamPCP
- **Targets:** npm, PyPI, Packagist/Composer ecosystems (1,800+ repositories compromised)
- **Impact:** ~930,000 combined weekly downloads across all three ecosystems

## Key Attack Characteristics

The attack differs from previous Shai-Hulud waves (September 2025, November 2025) in three critical ways:

1. **AI Coding Agent Persistence:** Abuses .claude/settings.json (Claude Code SessionStart hook) and .vscode/tasks.json (VSCode folderOpen trigger) to re-execute malware when repos are opened
2. **Russian Locale Evasion:** Exits cleanly if system locale is `ru` with log message
3. **Encrypted Exfiltration:** Data encrypted with AES-256-GCM; key wrapped with RSA-4096 (public key embedded in payload)

## Indicators of Compromise (IOCs)

| IOC Type | Value |
|----------|-------|
| **File: Loader** | setup.mjs |
| **SHA-256: Loader** | 4066781fa830224c8bbcc3aa005a396657f9c8f9016f9a64ad44a9d7f5f45e34 |
| **SHA-256: Payload (mbt)** | 80a3d2877813968ef847ae73b5eeeb70b9435254e74d7f07d8cf4057f0a710ac |
| **SHA-256: Payload (@cap-js/sqlite)** | 6f933d00b7d05678eb43c90963a80b8947c4ae6830182f89df31da9f568fea95 |
| **C2 Channel** | api.github.com (victim account repos) |
| **Exfil Repo Description** | A Mini Shai-Hulud has Appeared |
| **Binary Download Source** | github.com/oven-sh/bun/releases/download/bun-v1.3.13/ |
| **npm Registry Endpoint** | registry.npmjs.org |

## Dead-Drop Repository Name Pattern

Regex pattern for exfiltration repositories:
```
(sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\d{1,3}
```

## IDE Persistence File Indicators

| Indicator | Details |
|-----------|---------|
| **.vscode/tasks.json** | Contains "runOn": "folderOpen" and command "node .claude/setup.mjs" |
| **.claude/settings.json** | SessionStart hook running "node .vscode/setup.mjs" |
| **.claude/execution.js** | Payload copy (11.6 MB, single line of code) |
| **Commit Message** | "chore: update dependencies" |
| **Committer Email** | claude@users.noreply.github.com |

## Workflow Injection Indicators

| Indicator | Details |
|-----------|---------|
| **Branch Name** | dependabout/github_actions/format/setup-formatter |
| **Workflow File** | .github/workflows/format-check.yml |
| **Committer Email** | dependabot[bot]@users.noreply.github.com |
| **Artifact Name** | format-results |

## Code Signature Markers (Shai-Hulud Family)

| Marker | Value |
|--------|-------|
| **Cipher Salt** | ctf-scramble-v2 |
| **PBKDF2 Key** | 5012caa5847ae9261dfa16f91417042f367d6bed149c3b8af7a50b203a093007 |
| **Derived Master Key** | fd4b0f07b27e8f41bc70b8e2b79d168fb3fe80d7e0b37f43c506136a3418b44d |
| **Evasion Log String** | Exiting as russian language detected! |
| **Daemonize Environment Var** | \_\_DAEMONIZED |
| **GitHub PAT Regex** | gh[op]_[A-Za-z0-9]{36} |
| **npm Token Regex** | npm_[A-Za-z0-9]{36,} |
| **Bun Version (All Variants)** | 1.3.1313 |

## Detection Requirements

Create KQL queries to detect:

1. **File-based indicators:** Detection of setup.mjs, .claude/settings.json, .vscode/tasks.json, and .claude/execution.js creation or modification
2. **Hash-based detection:** Matches against the four provided SHA-256 file hashes
3. **Repository pattern matching:** Identification of repositories matching the dead-drop naming regex
4. **Credential exfiltration patterns:** GitHub PAT and npm token regex matches in process arguments, environment variables, or file contents
5. **IDE persistence mechanics:** Detection of VSCode/Claude Code configuration files with malicious hooks and folderOpen triggers
6. **Workflow injection:** Detection of suspicious GitHub Actions workflow files and commits from dependabot[bot]
7. **Process behavior:** Execution of node processes loading .claude/setup.mjs or .vscode/setup.mjs
8. **Network indicators:** Connections to api.github.com or registry.npmjs.org from unexpected contexts; downloads from github.com/oven-sh/bun/releases/download/bun-v1.3.13/
9. **Evasion indicators:** Processes checking system locale for "ru" or logging the evasion string
10. **Environment variable tampering:** Detection of \_\_DAEMONIZED environment variable usage

Note: Restore any defanged indicators to their original form in the final query output.

Prioritize detection of the IDE persistence mechanisms and dead-drop repository patterns, as these are novel vectors unique to this campaign iteration.