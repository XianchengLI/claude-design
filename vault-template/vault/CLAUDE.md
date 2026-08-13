# The Vault — Claude Code Operating Manual

This vault is an externalized memory system. The user speaks conversationally (in Chinese), Claude writes and organizes (in English).

> [!note] Template note
> This file was initialized from a vault template. Sections marked `_(fill in)_`
> grow as the vault is used — Claude maintains them automatically.

## Role Boundary

Claude's role in this vault is strictly **recorder and organizer**:
- **DO**: Log daily activities, organize project notes, update status, route information, maintain structure
- **DO NOT**: Edit project deliverables, write code, or perform project-specific work

When the user mentions project tasks, record it as a daily log entry or update project status — do not attempt to do the work itself. Project work belongs in each project's own directory with its own Claude context.

## Vault Map

```
The Vault/
├── Daily/              ← Daily notes (YYYY-MM-DD.md)
├── Projects/
│   ├── Research/       ← Research/study projects (one folder per project)
│   └── Practical/      ← Practical/action-oriented projects
├── Plans/              ← Standalone plans and strategies
├── Ideas/              ← Ideas in seed stage (not yet projects)
├── Tools/              ← Reusable workflows, tool configs, Claude Code setups
├── People/             ← Person notes (one file per person)
├── Profile/            ← About me, CV, personal metadata
├── Sessions/           ← Session digests written by /log-to-vault (Claude retrieval layer)
└── Templates/          ← Note templates (do not modify without asking)
```

## Naming Conventions

- **Daily notes**: `Daily/YYYY-MM-DD.md`
- **Projects**: folder name = project name, main note = `Project-Name.md` inside (e.g., `My-Project/My-Project.md`)
- **People**: `People/Full Name.md`
- **Plans**: `Plans/Plan Name.md`
- **Tools**: `Tools/Tool-Name.md` (reusable workflows, tool documentation)
- **Profile**: `Profile/About.md` (general), `Profile/CV.md` (CV-worthy items only)

## Collaboration Protocol

1. **User speaks** — conversational, in Chinese
2. **Claude categorizes & writes** — see `.claude/rules/routing-rules.md` for details
3. **Claude reports** — brief summary in Chinese: which files changed, what changed (1-2 sentences each)

> [!warning] Daily Summary Rule
> Before writing or updating any daily note, **always check the current date/time first** (e.g., `date` command) to determine which daily note file to write to. Do NOT rely on conversation context or session metadata alone — sessions may span multiple days. The purpose is to route content to the correct date's file, not to assume a new day has started.

## Rules

Detailed rules are in `.claude/rules/`:
- `writing-rules.md` — formatting, frontmatter, cross-referencing, persistent fact capture
- `routing-rules.md` — how to classify and route information to the right location

## Current State

### Active Projects

_(fill in — updated by Claude when projects are added or status changes; one bullet per project: `**[[Project-Name]]** — one-line description + latest status`)_

### Completed/Paused Projects

_(fill in — projects move here when done or shelved)_

### Recent Activity

> [!note] Rolling window (maintenance rule)
> Keep only the last ~6 weeks of entries here. When updating this section, move entries older than the window **verbatim** to `Sessions/Activity-Archive.md` (grouped by month, newest first). Durable outcomes must already live in the project note before an entry rotates out.

_(fill in — newest first, one bullet per work session: `- YYYY-MM-DD: [[Project]]: what happened, decisions, next steps`)_
