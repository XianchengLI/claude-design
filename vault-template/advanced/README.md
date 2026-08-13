# Advanced Add-ons (enable later, not on day 1)

These are maintenance tools that only pay off once the vault has real content
(roughly: 10+ notes, several weeks of use). Skip them during initial setup.

## 1. vault-health — structural audit skill

Checks broken wikilinks, active-project status drift, orphan notes, frontmatter
compliance, Recent Activity rotation.

**Install**: copy into the vault —
- `scripts/vault_health.py` → `<vault>/.claude/scripts/vault_health.py`
- `skills/vault-health/SKILL.md` → `<vault>/.claude/skills/vault-health/SKILL.md`

**No path edits needed** — the script locates the vault root relative to its own
location (`.claude/scripts/` → two levels up).

Run: `python .claude/scripts/vault_health.py` (or ask Claude for a "vault 体检").

## 2. Session indexing — auto-index of Claude Code sessions

`index_sessions.py` builds `Tools/Sessions-Index.md` (one line per session) from
the raw session logs; `find_sessions.py` locates session files across projects.

**Install**: copy both scripts to `<vault>/.claude/scripts/`, then **edit the
hardcoded constants** (they encode the vault's absolute path in slug form —
this is machine-specific and MUST be changed):

- `index_sessions.py` — `PROJECTS_DIR` and `INDEX_PATH` near the top:
  - slug format: `<drive>--Users-<username>-Documents-<Vault-Folder-Name>`
    (path with `\` and spaces replaced by `-`; check the actual folder name
    under `~/.claude/projects/` after running Claude in the vault once)
  - `INDEX_PATH` = `<vault>\Tools\Sessions-Index.md`
- `find_sessions.py` — `PROJECT_PREFIX` (same slug logic, without the vault name)

**Auto-run on session end** — add to `<vault>/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"<vault>/.claude/scripts/index_sessions.py\" --from-hook",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

(Requires Python on PATH. Use forward slashes or escaped backslashes in the path.)
