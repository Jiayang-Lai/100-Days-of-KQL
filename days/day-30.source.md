A mini shai-hulud campaign happened back in April 2026, which focused on SAP ecosystem.

Over a 48-hour window spanning April 29–30, 2026, a threat actor identified as TeamPCP compromised packages across npm, PyPI, and Packagist/Composer simultaneously, reaching approximately 1,800 repositories containing stolen credentials, with a combined weekly download exposure exceeding 930,000 across all three ecosystems.

# What Makes This Attack Different
This is the third wave of the Shai-Hulud campaign, following the original in September 2025 and The Second Coming in November 2025. Compared to those campaigns, this iteration differs in three key way:

## It persists through AI coding agent hooks
‍The payload commits a .claude/settings.json abusing Claude Code's SessionStart hook and a .vscode/tasks.json with "runOn": "folderOpen" into every accessible repo, signed claude@users.noreply.github.com with "chore: update dependencies". Anyone opening the repo in VSCode or Claude Code silently re-executes the malware. This is one of the first supply chain attacks to target AI coding agent configurations as a persistence and propagation vector.

## The malware exits on Russian-locale systems
‍If the system locale is ru, the payload logs "Exiting as russian language detected!" and exits cleanly. This CIS exemption is a well-known pattern among Eastern European actors and points to a Russia or CIS based operator.

## Stolen secrets are encrypted with an attacker-controlled key
Unlike previous waves, exfiltrated data is encrypted with AES-256-GCM and the key is wrapped using RSA-4096 with a public key embedded in the payload. Defenders who find the dead-drop repo see only ciphertext, so victims must assume worst case.

# Indicators of Compromise

## Files

- Loader (identical across packages) setup.mjs
- Loader SHA-256 4066781fa830224c8bbcc3aa005a396657f9c8f9016f9a64ad44a9d7f5f45e34
- Payload SHA-256 (mbt) 80a3d2877813968ef847ae73b5eeeb70b9435254e74d7f07d8cf4057f0a710ac
- Payload SHA-256 (@cap-js/sqlite) 6f933d00b7d05678eb43c90963a80b8947c4ae6830182f89df31da9f568fea95

## Network

- C2 channel api.github.com (repos under victim account)
- Exfil repo description A Mini Shai-Hulud has Appeared
- Live exfil search [github.com/search?q="A+Mini+Shai-Hulud+has+Appeared"&type=repositories](https://github.com/search?q=%22A+Mini+Shai-Hulud+has+Appeared%22&type=repositories)
- Bun runtime download github.com/oven-sh/bun/releases/download/bun-v1.3.13/
- npm publish endpoint https://registry.npmjs.org/ (worm propagation)

## Dead-Drop Repository Name Pattern

- Regex (sardaukar|mentat|fremen|atreides|harkonnen|gesserit|prescient|fedaykin|tleilaxu|siridar|kanly|sayyadina|ghola|powindah|prana|kralizec)-(sandworm|ornithopter|heighliner|stillsuit|lasgun|sietch|melange|thumper|navigator|fedaykin|futar|slig|phibian|laza|cogitor|ghola)-\\d{1,3}

## IDE Persistence Indicators

- VSCode task file .vscode/tasks.json with "runOn": "folderOpen" and command "node .claude/setup.mjs"
- Claude Code hook file .claude/settings.json with SessionStart hook running "node .vscode/setup.mjs"
- Payload copy .claude/execution.js (11.6 MB, single line)
- Commit message chore: update dependencies
- Committer email claude@users.noreply.github.com

## Workflow Injection Indicators

- Branch name dependabout/github\_actions/format/setup-formatter
- Workflow file .github/workflows/format-check.yml
- Committer (workflow) dependabot\[bot\]@users.noreply.github.com
- Artifact name format-results

## Code Markers (Shai-Hulud Family)

- Custom cipher salt ctf-scramble-v2
- PBKDF2 key 5012caa5847ae9261dfa16f91417042f367d6bed149c3b8af7a50b203a093007
- Derived master key fd4b0f07b27e8f41bc70b8e2b79d168fb3fe80d7e0b37f43c506136a3418b44d
- Evasion log string Exiting as russian language detected!
- Daemonize flag \_\_DAEMONIZED (env var)
- GitHub PAT regex /gh\[op\]\_\[A-Za-z0-9\]{36}/g
- npm token regex /npm\_\[A-Za-z0-9\]{36,}/g
- Bun version (all variants) 1.3.1313
