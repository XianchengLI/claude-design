"""
Session indexer for The Vault.

Reads Claude Code raw session jsonl files from
  ~/.claude/projects/EDIT-ME--your-vault-slug/*.jsonl
and writes a human-readable index to
  The Vault/Tools/Sessions-Index.md

Two modes:
  python index_sessions.py --all
    Rebuild the full index from scratch by scanning every jsonl file.

  python index_sessions.py --session <SESSION_ID>
    Upsert a single session into the index (used by the SessionEnd hook).
    If the session already has an entry it is replaced; otherwise a new
    entry is inserted under the correct date header.

Entry format (grouped by date, newest date first, newest session first):

  ## 2026-04-08
  - 12:24-13:24 · Review mempalace GitHub project · `4611415d` · 24 turns · Bash/Read/Write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects" / "EDIT-ME--your-vault-slug"
INDEX_PATH = Path(r"EDIT-ME:\path\to\your\vault\Tools\Sessions-Index.md")

INDEX_HEADER = """---
tags: [tool, index, sessions]
---

# Sessions Index

Auto-generated index of Claude Code sessions in **The Vault** project only.
Each entry: `start-end · ai-title · session-id · turns · tools`.

Raw session logs live in `~/.claude/projects/EDIT-ME--your-vault-slug/`.

## Related

- **Manual session digests** (Decisions / Facts / Gotchas per session):
  [[Sessions/{current_month}]]
- **Tool catalog**: [[Project-Tools-Index]]

## Tools

- **Rebuild this index**: `python .claude/scripts/index_sessions.py --all`
- **Cross-project search** (all 19 project dirs, not just vault):
  - `python .claude/scripts/find_sessions.py "query"`
  - `python .claude/scripts/find_sessions.py "Cohen" --word --project pd-pilot`
  - `python .claude/scripts/find_sessions.py --since 2026-03-20 --max 0` (list only)

The SessionEnd hook in `.claude/settings.json` keeps this file fresh
automatically — every time a vault session ends, its row is upserted.

"""


def parse_session(path: Path) -> dict | None:
    """Extract summary fields from one session jsonl file."""
    session_id = path.stem
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    ai_title: str | None = None
    assistant_turns = 0
    tools: dict[str, int] = {}
    cwd: str | None = None
    first_user_text: str | None = None

    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_str = d.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if first_ts is None or ts < first_ts:
                            first_ts = ts
                        if last_ts is None or ts > last_ts:
                            last_ts = ts
                    except ValueError:
                        pass

                t = d.get("type")
                if t == "ai-title":
                    ai_title = d.get("aiTitle") or ai_title
                elif t == "assistant":
                    assistant_turns += 1
                    msg = d.get("message", {}) or {}
                    content = msg.get("content")
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "tool_use":
                                name = c.get("name", "?")
                                tools[name] = tools.get(name, 0) + 1
                elif t == "user":
                    if cwd is None:
                        cwd = d.get("cwd")
                    if first_user_text is None:
                        msg = d.get("message", {}) or {}
                        content = msg.get("content")
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    txt = (c.get("text") or "").strip()
                                    # Skip tool-result-like and system messages
                                    if txt and not txt.startswith("<"):
                                        first_user_text = txt[:80]
                                        break
                        elif isinstance(content, str) and content.strip():
                            first_user_text = content.strip()[:80]
    except OSError:
        return None

    if first_ts is None:
        return None

    # Convert to local time for display (user is in Europe/London area but we
    # just use the wall-clock portion of the timestamp as-is — timestamps are
    # UTC in the jsonl, but the user's frame of reference for "when did that
    # happen" is local. We keep it simple: use UTC and rely on the user to
    # interpret. If this turns out wrong we can add tz handling later.)
    first_local = first_ts.astimezone()
    last_local = last_ts.astimezone() if last_ts else first_local

    title = ai_title or first_user_text or "(untitled)"
    # Strip newlines from title
    title = re.sub(r"\s+", " ", title).strip()

    return {
        "session_id": session_id,
        "short_id": session_id.split("-")[0],
        "date": first_local.strftime("%Y-%m-%d"),
        "start": first_local.strftime("%H:%M"),
        "end": last_local.strftime("%H:%M"),
        "title": title,
        "turns": assistant_turns,
        "tools": tools,
        "cwd": cwd,
        "mtime": path.stat().st_mtime,
    }


def format_entry(s: dict) -> str:
    """Render one session as a single markdown line."""
    tool_names = "/".join(sorted(s["tools"].keys())) if s["tools"] else "-"
    return (
        f"- {s['start']}-{s['end']} · {s['title']} · "
        f"`{s['short_id']}` · {s['turns']} turns · {tool_names}"
    )


def rendered_header() -> str:
    """Fill dynamic placeholders in INDEX_HEADER (e.g. current_month)."""
    current_month = datetime.now().strftime("%Y-%m")
    return INDEX_HEADER.replace("{current_month}", current_month)


def build_full_index() -> str:
    """Scan all jsonl files and build the full index text."""
    if not PROJECTS_DIR.exists():
        print(f"[warn] {PROJECTS_DIR} does not exist", file=sys.stderr)
        return rendered_header()

    sessions = []
    for p in PROJECTS_DIR.glob("*.jsonl"):
        s = parse_session(p)
        if s is not None:
            sessions.append(s)

    # Group by date, newest first; within a date, newest session first
    by_date: dict[str, list[dict]] = {}
    for s in sessions:
        by_date.setdefault(s["date"], []).append(s)
    for day in by_date.values():
        day.sort(key=lambda x: x["start"], reverse=True)

    parts = [rendered_header()]
    for date in sorted(by_date.keys(), reverse=True):
        parts.append(f"## {date}\n")
        for s in by_date[date]:
            parts.append(format_entry(s))
        parts.append("")
    return "\n".join(parts) + "\n"


def upsert_session(session_id: str) -> None:
    """Insert or replace one session's entry in the existing index."""
    path = PROJECTS_DIR / f"{session_id}.jsonl"
    if not path.exists():
        print(f"[warn] session file not found: {path}", file=sys.stderr)
        return
    s = parse_session(path)
    if s is None:
        print(f"[warn] could not parse {path}", file=sys.stderr)
        return

    new_line = format_entry(s)
    date_header = f"## {s['date']}"
    short_id_marker = f"`{s['short_id']}`"

    if not INDEX_PATH.exists():
        INDEX_PATH.write_text(build_full_index(), encoding="utf-8")
        return

    text = INDEX_PATH.read_text(encoding="utf-8")

    # Self-heal: if the header block was ever lost (file no longer starts with
    # frontmatter), incremental upserts would silently accumulate blank lines
    # at the top forever. Fall back to a full rebuild instead.
    if not text.startswith("---"):
        INDEX_PATH.write_text(build_full_index(), encoding="utf-8")
        return

    # Keep the "current month" wikilink in the Related section fresh across
    # month boundaries, so the link always points at the month the user is
    # most likely looking for. Matches `[[Sessions/YYYY-MM]]` and rewrites
    # just the YYYY-MM part.
    current_month = datetime.now().strftime("%Y-%m")
    text = re.sub(
        r"\[\[Sessions/\d{4}-\d{2}\]\]",
        f"[[Sessions/{current_month}]]",
        text,
        count=1,
    )

    lines = text.splitlines()

    # Remove any existing entry for this session id
    lines = [ln for ln in lines if short_id_marker not in ln]

    # Find the date header, or insert one in the right place
    try:
        header_idx = lines.index(date_header)
    except ValueError:
        # Insert a new date section in descending-date order
        insert_at = len(lines)
        for i, ln in enumerate(lines):
            m = re.match(r"^## (\d{4}-\d{2}-\d{2})\s*$", ln)
            if m and m.group(1) < s["date"]:
                insert_at = i
                break
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, date_header)
        lines.insert(insert_at + 2, "")
        header_idx = insert_at + 1

    # Insert new_line right after the date header (newest within day on top)
    lines.insert(header_idx + 1, new_line)

    INDEX_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Index Claude Code sessions for The Vault")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="Rebuild full index")
    g.add_argument("--session", metavar="ID", help="Upsert a single session by id")
    g.add_argument(
        "--from-hook",
        action="store_true",
        help="Read Claude Code hook JSON from stdin and upsert that session",
    )
    args = ap.parse_args()

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.all:
        INDEX_PATH.write_text(build_full_index(), encoding="utf-8")
        print(f"[ok] rebuilt {INDEX_PATH}")
    elif args.from_hook:
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"[warn] could not parse hook stdin: {e}", file=sys.stderr)
            return
        session_id = payload.get("session_id")
        if not session_id:
            print("[warn] hook payload missing session_id", file=sys.stderr)
            return
        upsert_session(session_id)
        print(f"[ok] hook: upserted {session_id} into {INDEX_PATH}")
    else:
        upsert_session(args.session)
        print(f"[ok] upserted session {args.session} into {INDEX_PATH}")


if __name__ == "__main__":
    main()
