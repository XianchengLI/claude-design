---
name: lit-mcp
description: Toggle the literature MCP servers (academic-search + zotero) for the current project. Use when the user says /lit-mcp on|off|status, wants to start or finish a literature-work phase, or when citation/Zotero MCP tools are needed but not loaded in this project.
---

# lit-mcp — per-project literature MCP toggle

The literature MCP servers (`academic-search`, `zotero`) are NOT configured
globally (each loaded copy costs ~300 MB per session). They are enabled
per project, on demand, via local-scope config.

## Action

Parse the argument as `on`, `off`, or `status` (default: `status`), then run
from the project root:

```
powershell -NoProfile -File C:\Users\Xianc\.claude\scripts\lit-mcp.ps1 <action>
```

The script must run with the current working directory = the project that
should get (or lose) the servers, because `claude mcp add -s local` binds to cwd.

## After running

- `on` / `off`: tell the user (in Chinese) that the change only takes effect
  in a NEW Claude Code session — MCP servers load at session start; there is
  no mid-session load. Already-open sessions are unaffected.
- If the user needs the tools immediately, the path is: `on` → restart the
  session → tools available via ToolSearch.

## Notes

- API keys live inside the script; do not copy them into vault notes or repos.
- The retired global `memory` MCP (knowledge-graph server) is gone by design;
  hooks read `~/.claude/memory.json` directly and do not need it. To restore:
  `claude mcp add memory -s user -- cmd /c npx -y @modelcontextprotocol/server-memory --file C:/Users/Xianc/.claude/memory.json`
