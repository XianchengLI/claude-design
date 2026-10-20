"""Shared helpers for the multi-session tower kit: locate the project, load tower.json, resolve paths.

Project lookup: --project DIR > env TOWER_PROJECT > walk up from cwd until a tower.json is found.
No config -> exit code 3 with a one-line message (the project has not opted in).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
CONFIG_NAME = "tower.json"

DEFAULTS = {
    "project": None,
    "level": 2,
    "files": {
        "sessions": "notes/SESSIONS.md",
        "tasks": "notes/tasks.md",
        "handover": "notes/handover.md",
        "inbox": "notes/CLAUDE_inbox.md",
        "tower_log": "notes/tower_log.md",
        "memory": "MEMORY.md",
        "claude_md": "CLAUDE.md",
        "decisions": "notes/decisions.md",
        "gotchas": "notes/gotchas.md",
        "judge_dir": "data/judge_bundles",
    },
    "task_sections": {"doing": "In progress", "queue": "Queue", "done": "Done"},
    "shared_files": [],
    "code_repos": [],
    "stale_hours": 2.0,
    "dead_hours": 24.0,
    "limits": {
        "max_workers": 3,
        "max_heavy": 1,
        "ctx_soft_k": 150,
        "ctx_hard_k": 200,
        "start_card_minutes": 15,
        "claude_md_chars": 15000,
    },
    "timesheet": False,
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def find_root(explicit: str | None = None, start: str | None = None) -> Path | None:
    for cand in (explicit, os.environ.get("TOWER_PROJECT")):
        if cand and (Path(cand) / CONFIG_NAME).exists():
            return Path(cand).resolve()
    p = Path(start or Path.cwd()).resolve()
    for d in (p, *p.parents):
        if (d / CONFIG_NAME).exists():
            return d
    return None


def load(root: Path) -> dict:
    raw = json.loads((root / CONFIG_NAME).read_text(encoding="utf-8"))
    cfg = _merge(DEFAULTS, raw)
    cfg["project"] = cfg["project"] or root.name
    return cfg


def path(root: Path, cfg: dict, key: str) -> Path:
    return root / cfg["files"][key]


def pop_project_arg(argv: list[str]) -> str | None:
    """Remove '--project DIR' from argv in place and return DIR."""
    if "--project" in argv:
        i = argv.index("--project")
        val = argv[i + 1] if i + 1 < len(argv) else None
        del argv[i : i + 2]
        return val
    return None


def utf8_stdio():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
