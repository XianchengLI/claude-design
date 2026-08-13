"""
Cross-project session search.

Searches all Claude Code session jsonl files under
  ~/.claude/projects/EDIT-ME--your-documents-slug-*/
for a substring query and returns matches grouped by project and session.

Usage:
  python find_sessions.py "Anna"
  python find_sessions.py "Cohen's d" --project pd-pilot
  python find_sessions.py "JBHI" --since 2026-03-15 --until 2026-03-31
  python find_sessions.py --project vault --max 0   # list all sessions, no body match
  python find_sessions.py "fig 3" --context 120 --max 5

Each match prints: project, session date+time, ai-title, session id, then up to
--max matching snippets per session (default 3) with --context chars on each
side of the hit.

Designed to be fast on ~270MB across ~60 jsonl files: each line is first checked
with a cheap substring filter on the raw bytes, and only matching lines are
json-parsed for text extraction.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 stdout so Chinese / non-ASCII content prints correctly on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

PROJECTS_ROOT = Path.home() / ".claude" / "projects"
PROJECT_PREFIX = "EDIT-ME--your-documents-slug-"


def project_name(dir_name: str) -> str:
    """Strip the EDIT-ME--your-documents-slug- prefix to get a readable name."""
    return dir_name[len(PROJECT_PREFIX):] if dir_name.startswith(PROJECT_PREFIX) else dir_name


def iter_text_in_message(d: dict):
    """Yield all string text inside a user/assistant message entry."""
    msg = d.get("message")
    if not isinstance(msg, dict):
        return
    content = msg.get("content")
    if isinstance(content, str):
        yield content
        return
    if not isinstance(content, list):
        return
    for c in content:
        if not isinstance(c, dict):
            continue
        ctype = c.get("type")
        if ctype == "text":
            t = c.get("text")
            if isinstance(t, str):
                yield t
        elif ctype == "tool_use":
            inp = c.get("input")
            if isinstance(inp, dict):
                for v in inp.values():
                    if isinstance(v, str):
                        yield v
        elif ctype == "tool_result":
            tr = c.get("content")
            if isinstance(tr, str):
                yield tr
            elif isinstance(tr, list):
                for item in tr:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        yield item["text"]


def extract_session_meta(path: Path) -> dict:
    """Quick scan for ai-title, first/last timestamps, first user text."""
    meta = {
        "session_id": path.stem,
        "short_id": path.stem.split("-")[0],
        "ai_title": None,
        "first_ts": None,
        "last_ts": None,
        "first_user": None,
    }
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
                ts = d.get("timestamp")
                if ts:
                    if meta["first_ts"] is None:
                        meta["first_ts"] = ts
                    meta["last_ts"] = ts
                t = d.get("type")
                if t == "ai-title" and meta["ai_title"] is None:
                    meta["ai_title"] = d.get("aiTitle")
                elif t == "user" and meta["first_user"] is None:
                    for txt in iter_text_in_message(d):
                        s = txt.strip()
                        if s and not s.startswith("<") and "tool_use_id" not in s[:30]:
                            meta["first_user"] = s[:80]
                            break
    except OSError:
        pass
    return meta


def fmt_ts(ts: str | None) -> str:
    if not ts:
        return "????-??-?? ??:??"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts[:16]


def make_snippet(text: str, query_lower: str, ctx: int) -> str:
    idx = text.lower().find(query_lower)
    if idx < 0:
        return text[: 2 * ctx]
    start = max(0, idx - ctx)
    end = min(len(text), idx + len(query_lower) + ctx)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + snippet + suffix


def search_session(
    path: Path,
    query: str | None,
    ctx: int,
    max_per_session: int,
    word: bool = False,
) -> list[dict]:
    """Return list of matches for one session file. Empty list = no match."""
    if query is None:
        return []
    query_lower = query.lower()
    word_re = re.compile(r"\b" + re.escape(query_lower) + r"\b", re.IGNORECASE) if word else None

    def hit(text: str) -> bool:
        return bool(word_re.search(text)) if word_re else (query_lower in text.lower())

    matches = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                # Cheap pre-filter on the raw line first; we still need to verify
                # against the parsed text content for word-boundary mode and to
                # extract a snippet.
                if query_lower not in line.lower():
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = d.get("type")
                if t not in ("user", "assistant"):
                    continue
                for text in iter_text_in_message(d):
                    if hit(text):
                        matches.append({
                            "ts": d.get("timestamp"),
                            "role": t,
                            "snippet": make_snippet(text, query_lower, ctx),
                        })
                        if max_per_session and len(matches) >= max_per_session:
                            return matches
                        break
    except OSError:
        pass
    return matches


def date_in_range(ts: str | None, since: str | None, until: str | None) -> bool:
    if not ts:
        return True
    day = ts[:10]
    if since and day < since:
        return False
    if until and day > until:
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Search Claude Code sessions across all projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("query", nargs="?", help="Substring to search (case-insensitive). Omit to just list sessions.")
    ap.add_argument("--project", help="Filter by project name substring")
    ap.add_argument("--since", help="Only sessions on/after YYYY-MM-DD")
    ap.add_argument("--until", help="Only sessions on/before YYYY-MM-DD")
    ap.add_argument("--max", type=int, default=3, help="Max snippets per session (0 = no body match, just list)")
    ap.add_argument("--context", type=int, default=80, help="Chars of context around match")
    ap.add_argument("--word", action="store_true", help="Match whole words only (avoids 'Anna' matching 'planName')")
    args = ap.parse_args()

    if not PROJECTS_ROOT.exists():
        print(f"[error] {PROJECTS_ROOT} not found", file=sys.stderr)
        sys.exit(1)

    project_dirs = sorted(
        p for p in PROJECTS_ROOT.iterdir()
        if p.is_dir() and p.name.startswith(PROJECT_PREFIX)
    )
    if args.project:
        needle = args.project.lower()
        project_dirs = [p for p in project_dirs if needle in project_name(p.name).lower()]

    total_sessions = 0
    total_matches = 0

    for proj_dir in project_dirs:
        jsonls = sorted(proj_dir.glob("*.jsonl"))
        if not jsonls:
            continue

        proj_results = []  # list of (meta, matches)
        for jp in jsonls:
            meta = extract_session_meta(jp)
            if not date_in_range(meta["first_ts"], args.since, args.until):
                continue
            if args.query and args.max > 0:
                matches = search_session(jp, args.query, args.context, args.max, args.word)
                if not matches:
                    continue
            else:
                matches = []
                if args.query and args.max == 0:
                    # body filter requested with max 0: skip body, but require query
                    # to appear anywhere in raw file
                    try:
                        if args.query.lower() not in jp.read_text(encoding="utf-8", errors="ignore").lower():
                            continue
                    except OSError:
                        continue
            proj_results.append((meta, matches))
            total_sessions += 1
            total_matches += len(matches)

        if not proj_results:
            continue

        print(f"\n=== {project_name(proj_dir.name)} ({len(proj_results)} sessions) ===")
        # newest first
        proj_results.sort(key=lambda x: x[0]["first_ts"] or "", reverse=True)
        for meta, matches in proj_results:
            title = meta["ai_title"] or meta["first_user"] or "(untitled)"
            title = re.sub(r"\s+", " ", title).strip()
            print(f"  {fmt_ts(meta['first_ts'])} · {title} · `{meta['short_id']}`")
            for m in matches:
                role = m["role"][0].upper()  # U or A
                t = fmt_ts(m["ts"]).split(" ")[1] if m["ts"] else "??:??"
                print(f"      [{role} {t}] {m['snippet']}")

    if args.query:
        print(f"\n[summary] {total_matches} matches across {total_sessions} sessions for {args.query!r}")
    else:
        print(f"\n[summary] {total_sessions} sessions matched filters")


if __name__ == "__main__":
    main()
