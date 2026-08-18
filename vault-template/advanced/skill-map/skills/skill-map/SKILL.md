---
name: skill-map
description: Regenerate the Skills/ inventory notes from all installed Claude Code skills, commands, and enabled plugins. Use when the user asks to update the skill map / skill 图谱, after installing or removing skills, or asks what skills they have and how each is invoked.
---

# Skill Map

Regenerates the two-layer skill inventory under `Skills/` (one note per
skill + category hubs + `Skill-Index.md` entry point — named Index, not Map,
because `Skill-Map.md` would case-collide with the `skill-map.md` leaf on
Windows). The Obsidian graph renders each category hub as a large node with
its skills around it.

## Run

```
python .claude/scripts/skill_map.py            # generate/update + report
python .claude/scripts/skill_map.py --dry-run  # preview only
```

## How it works

- Scans: global `~/.claude/skills` + `~/.claude/commands`, every
  `Documents/*/.claude/skills|commands`, and skills/commands of plugins
  enabled in `settings.json`.
- **Machine layer** (above `%% MANUAL %%` in each note) is regenerated on
  every run. **Human layer** (below the marker) is always preserved — usage
  notes, gotchas, refinements live there.
- Category assignment: `.claude/scripts/skill_map_config.json`. New skills
  with no category land in an `Uncategorized` hub and are reported — assign
  them in the config, re-run.
- Disappeared skills get `status: removed` in frontmatter; the note is kept
  until the user deletes it.

## Interpreting results

Report in Chinese: created/updated counts, any UNCATEGORIZED names (propose
a category for each, wait for confirmation before editing the config), any
MARKED REMOVED (ask whether to delete the note), any IN CONFIG BUT NOT ON
DISK (stale config entries — propose removal).

Never edit the machine layer of a note by hand; fix the script or config
instead. Manual knowledge goes below the marker.

## Cadence

After installing/removing any skill or plugin; otherwise monthly alongside
/vault-health.
