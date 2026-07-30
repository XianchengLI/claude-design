# MCP (Model Context Protocol) Guide

> Date: 2026-02-17

## What is MCP

MCP is an open protocol that lets Claude call external programs/services through a standardized interface. Each MCP server is an **independent process** that provides structured tools to Claude.

**Not a code library** — Claude doesn't run MCP code. It sends requests to a separate process and receives structured results.

## Architecture

```
Claude Code (MCP Client)
  ├── Native tools: Read, Write, Edit, Bash, WebSearch, WebFetch...
  ├── MCP Server: memory   → create_entities, search_nodes...
  ├── MCP Server: sqlite   → query, list_tables...
  └── MCP Server: github   → create_pr, list_issues...
```

### Data flow (each tool call)

```
Claude ──JSON-RPC request──→ MCP Server ──actual work──→ External Resource
Claude ←─JSON-RPC response── MCP Server ←─results────── (DB, API, file...)
```

- Every tool call = one round-trip between two processes
- MCP server handles all actual work (DB connection, API auth, data formatting)
- Claude only sends parameters and receives structured results

### Two deployment modes

| Mode | Transport | MCP server runs on | Can access local files? |
|------|-----------|-------------------|------------------------|
| **Local** (most common) | stdio (subprocess) | Your machine | Yes |
| **Remote** | HTTP/SSE | Someone else's server | No (only their resources) |

## MCP vs Other Claude Code Concepts

| Concept | What it is | Adds new capabilities? | Context cost |
|---------|-----------|----------------------|-------------|
| **Rules** (CLAUDE.md) | Persistent instructions | No | Full text every session |
| **Skills** (SKILL.md) | Prompt engineering | No (guidance only) | ~1 line description |
| **Hooks** (JS) | Lifecycle automation | No (external scripts) | Zero |
| **MCP** | Capability extension | **Yes (new tools)** | **All tool definitions injected** |
| **Prompts** | Reusable prompt templates | No | Only when Read |

### MCP vs Bash

| | Bash | MCP |
|--|------|-----|
| Who writes the logic? | Claude (generates scripts) | MCP server author (pre-built) |
| Who executes it? | Shell process | MCP server process |
| Communication | Text in, text out | Structured JSON in/out |
| State | Stateless (new process each time) | **Stateful** (persistent connection) |
| Claude's effort | Write code + parse text output | Just pass parameters, receive results |

## When MCP is Worth It

**Use MCP when:**
- High-frequency calls to the same service (database queries, API calls)
- Need persistent state (DB connection, auth session, cache)
- Structured data is important (avoid parsing text output)
- Claude doesn't know how to write the integration code

**Skip MCP when:**
- WebFetch or Bash can do it in 1-2 calls
- One-off operations (no state needed)
- The service is simple enough for Claude to script directly

**Core test:** If `WebFetch` + `Bash` can do it, you don't need MCP.

## Installation & Distribution

MCP servers are distributed as packages, most commonly via npm:

```json
{
  "memory": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-memory"]
  }
}
```

`npx -y` = auto-download to npm cache if not present, then run. No manual install step.

| Distribution method | Command | Notes |
|--------------------|---------|-------|
| **npx** (most common) | `npx -y @some/mcp-server` | Auto-download + run |
| npm global install | `npm install -g` then `node server.js` | Faster startup |
| Python (uvx/pip) | `uvx some-mcp-server` | Python ecosystem |
| Docker | `docker run some-mcp-server` | Isolated environment |
| Remote HTTP | Just a URL, nothing to download | Zero local install |

Cache location (Windows): `C:\Users\<user>\AppData\Local\npm-cache\_npx\`

## Context Cost

Every enabled MCP server injects **all its tool definitions** into Claude's context at session start. The memory MCP adds 8 tool definitions (~500 tokens). This cost is paid whether or not the tools are used.

**To avoid wasted context:** only configure MCP servers you actively use. Store configs for occasional-use servers in a reference file and add them to `~/.claude/mcp.json` when needed.

## Current Setup Decision (2026-02-17)

- **memory MCP**: not configured by default (save config for manual enable when needed)
- **everything-claude-code plugin**: pending removal (disabled but files remain)
- **Rationale**: current workflow (data analysis + paper writing) is fully covered by native tools + skills. No MCP server provides enough value to justify the context cost.

### Re-enable memory MCP when needed

Add to `~/.claude/mcp.json`:
```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```
Then restart session. Remove the config and restart to disable.
