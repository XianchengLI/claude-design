# Claude Design - Learning & Reference Collection

Resources, patterns, and notes on designing effective Claude Code workflows.

## Contents

| File | Topic | Source | Date |
|------|-------|--------|------|
| [skill-design-patterns.md](skill-design-patterns.md) | SKILL.md structure template & 6 design patterns | [notebooklm-skill](https://github.com/PleasePrompto/notebooklm-skill), Pividori 2024 | 2026-02-16 |
| [skill-cleanup-log.md](skill-cleanup-log.md) | K-Dense skill cleanup: before/after line counts, decisions, lessons | [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills) | 2026-02-16 |
| [mcp-guide.md](mcp-guide.md) | MCP architecture, vs Skills/Hooks/Bash, when to use, installation, context cost | Discussion notes | 2026-02-17 |
| [onboarding-guide-zh.md](onboarding-guide-zh.md) | Standalone Chinese onboarding guide (share-ready): full architecture, commands/skills/MCP/hooks, work patterns, 0-to-1 path | Written for a friend new to Claude Code | 2026-08-04 |
| [vault-template/](vault-template/) | Reusable skeleton of the personal-vault system (Obsidian + Claude Code): folder structure, CLAUDE.md operating manual, routing/writing rules, `/vault` + `/log-to-vault` commands (parameterized), optional vault-health & session-index add-ons. Chinese setup guide inside | Extracted & sanitized from The Vault | 2026-08-13 |
| [skills/skill-adoption/](skills/skill-adoption/) | Installable skill: 10-rule workflow for evaluating/installing/upgrading third-party skills — content-level comparison, bidirectional cross-optimization, soft-dependency inspection, customization-preserving upgrades, security scanning, SKIP/lineage registries | Distilled from a real multi-pack adoption day; every rule from an actual mistake | 2026-08-18 |
| [skills/academic-literature-skills/](skills/academic-literature-skills/) | Two installable skills for literature work: `literature-review` (systematic search → screening → thematic synthesis, source pointers on load-bearing claims) + `citation-management` (3-stage verification, reference ledger with hard metrics, BibTeX validator that catches wrong-paper DOIs) — [zip](skills/academic-literature-skills.zip) | Based on K-Dense-AI/claude-scientific-skills, substantially extended from real manuscript audits | 2026-08-19 |
| [vault-template/advanced/skill-map/](vault-template/advanced/skill-map/) | Vault add-on: living inventory of every installed skill/command — generator script + two-layer notes (machine/manual) + category hubs + graph view + Candidate-Skills / Skill-Lineage registry templates | Extracted & sanitized from The Vault | 2026-08-18 |

Update history: [CHANGELOG.md](CHANGELOG.md) (简单易懂版更新日志)
