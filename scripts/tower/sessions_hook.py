#!/usr/bin/env python3
"""SESSIONS table: who is working on what, right now (multi-session coordination).

Generic version of capp-career-agent/scripts/sessions_hook.py, driven by <project>/tower.json.
Claude Code hook entry point; start / end / check read the hook JSON from stdin.

  start   SessionStart   register this session (if absent), retire dead rows, print the table,
                         the task-list summary, worktrees of code_repos, and a CLAUDE.md budget warning
  end     SessionEnd     remove this session's row
  check   PreToolUse Edit|Write|MultiEdit
                         exit 2 (= block the write) when the target is claimed by another live session,
                         or when CLAUDE.md is written by a session that does not hold the main mark
  show    (manual)       print the table

  python sessions_hook.py --project <root> start|end|check|show

Row: | started | session | topic | branch / worktree | claims | main |
  session  first 8 chars of the session id; "-" = manual row (never retired, always live)
  claims   repo-relative paths, comma separated; trailing "/" claims a directory
  main     "✓" = the one session allowed to edit CLAUDE.md (a write right, NOT the tower role)

Liveness = mtime of the transcript (~/.claude/projects/*/<id>*.jsonl):
  idle > stale_hours -> shown idle, claims stop blocking;  idle > dead_hours -> row retired at next start.
`check` fails open: any exception -> exit 0 (a hook bug never blocks work).
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tower_common as tc  # noqa: E402

TRANSCRIPTS = Path.home() / ".claude" / "projects"
NCOLS = 6
HEADER_LINE = "| started | session | topic | branch / worktree | claims | main |"
SEP_LINE = "|---|---|---|---|---|---|"
SPLIT = re.compile(r"[,，、;；]")

ROOT: Path
CFG: dict


def preamble():
    inbox = CFG["files"]["inbox"]
    return [
        "# SESSIONS · who is working on what, right now",
        "",
        "> Maintained by the tower kit hook: SessionStart registers a row, SessionEnd removes it; "
        f"a transcript idle > {CFG['stale_hours']:g} h = idle (claims stop blocking), > {CFG['dead_hours']:g} h = row retired.",
        "> Claude fills three cells once it knows the task: topic (end with `· agent <name from ListAgents>` if messaging is used) / "
        "branch / claims (files it will rewrite wholesale). Shared files are never claimed: re-read, anchor-append only.",
        f"> Writes to another session's claims are blocked; only the `main` ✓ session may edit CLAUDE.md, others write rules to `{inbox}`.",
        "> The control tower is the row whose topic says `control tower`; ✓ is only the CLAUDE.md write right. Not committed to git.",
        "",
        HEADER_LINE,
        SEP_LINE,
    ]


class Row:
    __slots__ = ("start", "sid", "topic", "branch", "files", "main")

    def __init__(self, cells):
        cells = [c.strip() for c in cells]
        cells += [""] * (NCOLS - len(cells))
        self.start, self.sid, self.topic, self.branch, self.files, self.main = cells[:NCOLS]

    def line(self):
        return "| " + " | ".join([self.start, self.sid, self.topic, self.branch, self.files, self.main]) + " |"


def short(sid):
    return (sid or "").strip()[:8] or "?"


def norm(p):
    return os.path.normcase(os.path.normpath(str(Path(p).resolve())))


def table_path():
    return tc.path(ROOT, CFG, "sessions")


def load():
    t = table_path()
    text = t.read_text(encoding="utf-8") if t.exists() else "\n".join(preamble()) + "\n"
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    sep = next((i for i, l in enumerate(lines) if l.strip().startswith("|---")), None)
    if sep is None:
        lines = preamble()
        sep = len(lines) - 1
    head = lines[: sep + 1]
    rows = []
    for l in lines[sep + 1:]:
        if l.strip().startswith("|"):
            r = Row(l.strip().strip("|").split("|"))
            if r.sid:
                rows.append(r)
    return head, rows, nl


def save(head, rows, nl):
    t = table_path()
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text(nl.join(head + [r.line() for r in rows]) + nl, encoding="utf-8", newline="")


def transcript_age_h(sid):
    if sid == "-":
        return 0.0
    paths = glob.glob(str(TRANSCRIPTS / "*" / (glob.escape(sid) + "*.jsonl")))
    if not paths:
        return None
    return (time.time() - max(os.path.getmtime(p) for p in paths)) / 3600.0


def start_age_h(row):
    try:
        t = datetime.strptime(f"{datetime.now().year}-{row.start}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    age = (datetime.now() - t).total_seconds() / 3600.0
    return age if age >= 0 else age + 365 * 24.0


def status(row):
    """(label, blocks)."""
    if row.sid == "-":
        return "manual", True
    age = transcript_age_h(row.sid)
    if age is None:
        sa = start_age_h(row)
        return ("dead", False) if sa is not None and sa > CFG["dead_hours"] else ("unknown", True)
    if age > CFG["dead_hours"]:
        return "dead", False
    if age > CFG["stale_hours"]:
        return f"idle {age:.1f} h", False
    return "live", True


def claims(cell):
    out = []
    for raw in SPLIT.split(cell or ""):
        tok = raw.strip().strip("`").strip()
        if not tok:
            continue
        tok = tok.split()[0].strip("`")
        if not tok or "§" in tok:
            continue
        is_dir = tok.endswith(("/", "\\"))
        p = Path(tok)
        if not p.is_absolute():
            p = ROOT / tok
        s = norm(p)
        if not is_dir and os.path.isdir(s):
            is_dir = True
        out.append((s, is_dir))
    return out


def deny(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(2)


def render(rows, own_sid):
    out = [HEADER_LINE + " status |", SEP_LINE + "---|"]
    for r in rows:
        label = "this session" if r.sid == own_sid else status(r)[0]
        out.append(r.line() + f" {label} |")
    return out


def tasks_summary(max_queue=8, width=150):
    """All 'doing' rows + the first max_queue 'queue' rows, each cut to width chars."""
    t = tc.path(ROOT, CFG, "tasks")
    if not t.exists():
        return []
    text = t.read_text(encoding="utf-8")
    names = CFG["task_sections"]

    def section(name):
        m = re.search(r"^## " + re.escape(name) + r".*?$(.*?)(?=^## |\Z)", text, re.S | re.M)
        return m.group(1) if m else ""

    def body_rows(sec):
        rows = [l.rstrip() for l in sec.splitlines() if l.startswith("|")]
        return [l for l in rows[2:] if not l.startswith("|---")]

    doing, queue = body_rows(section(names["doing"])), body_rows(section(names["queue"]))
    rel = CFG["files"]["tasks"]
    out = [f"[TASKS] {rel} · {names['doing']} {len(doing)} · {names['queue']} {len(queue)} "
           "(one session = one row; move it to doing at start, to done at close)"]
    out += ["  " + l[:width] for l in doing]
    out += ["  " + l[:width] for l in queue[:max_queue]]
    if len(queue) > max_queue:
        out.append(f"  ... {len(queue) - max_queue} more, see file")
    return out


def worktrees():
    out = []
    for repo in CFG["code_repos"]:
        p = (ROOT / repo).resolve()
        try:
            r = subprocess.run(["git", "-C", str(p), "worktree", "list"], capture_output=True,
                               text=True, encoding="utf-8", timeout=8)
            if r.returncode == 0 and r.stdout.strip():
                out.append(f"[WORKTREES] {repo}")
                out += ["  " + l for l in r.stdout.strip().splitlines()]
        except Exception:
            pass
    return out


def budget_warning():
    cm = tc.path(ROOT, CFG, "claude_md")
    cap = CFG["limits"].get("claude_md_chars")
    if not cap or not cm.exists():
        return []
    n = len(cm.read_text(encoding="utf-8"))
    if n <= cap:
        return []
    return [f"[BUDGET] CLAUDE.md is {n:,} chars > budget {cap:,}. Every session pays this at startup. "
            "Before adding a rule: retire one, or turn it into a script/hook check."]


def cmd_start(data):
    sid = short(data.get("session_id"))
    head, rows, nl = load()
    kept, retired = [], []
    for r in rows:
        (retired if r.sid != sid and status(r)[0] == "dead" else kept).append(r)
    own = next((r for r in kept if r.sid == sid), None)
    out = []
    if own is None:
        main = "" if any(r.main for r in kept) else "✓"
        own = Row([datetime.now().strftime("%m-%d %H:%M"), sid, "", "", "", main])
        kept.append(own)
        out.append(f"[SESSIONS] session {sid} registered" + (" with main ✓ (may edit CLAUDE.md)" if main else "")
                   + f". Once the task is known, fill topic / branch / claims in {CFG['files']['sessions']}.")
    else:
        out.append(f"[SESSIONS] session {sid} ({own.topic or 'topic empty'})" + (", main ✓" if own.main else ""))
    save(head, kept, nl)
    out.extend(render(kept, sid) if len(kept) > 1 else ["[SESSIONS] no other live session."])
    if retired:
        out.append(f"[SESSIONS] retired {len(retired)} dead row(s): "
                   + ", ".join(f"{r.sid} ({r.topic or 'no topic'})" for r in retired))
    out += tasks_summary() + worktrees() + budget_warning()
    print("\n".join(out))


def cmd_end(data):
    sid = short(data.get("session_id"))
    head, rows, nl = load()
    kept = [r for r in rows if r.sid != sid]
    if len(kept) != len(rows):
        save(head, kept, nl)


def cmd_check(data):
    sid = short(data.get("session_id"))
    fp = (data.get("tool_input") or {}).get("file_path")
    if not fp:
        return
    target = Path(fp)
    if not target.is_absolute():
        target = Path(data.get("cwd") or os.getcwd()) / target
    target = norm(target)
    if target in (norm(table_path()), norm(tc.path(ROOT, CFG, "inbox"))):
        return
    head, rows, nl = load()
    if target == norm(tc.path(ROOT, CFG, "claude_md")):
        for r in rows:
            if r.sid != sid and r.main and status(r)[1]:
                deny(f"[SESSIONS] only the main session {r.sid} ({r.topic or 'topic empty'}) may edit CLAUDE.md. "
                     f"Write the rule to {CFG['files']['inbox']}; the tower merges it.")
    for r in rows:
        if r.sid == sid or not status(r)[1]:
            continue
        for entry, is_dir in claims(r.files):
            if target == entry or (is_dir and target.startswith(entry.rstrip("\\/") + os.sep)):
                rel = os.path.relpath(target, norm(ROOT)) if target.startswith(norm(ROOT)) else target
                deny(f"[SESSIONS] write to {rel} refused: claimed by session {r.sid} ({r.topic or 'topic empty'}). "
                     "Coordinate in the SESSIONS table (hand over / split / wait), or edit your own files.")


def main():
    global ROOT, CFG
    tc.utf8_stdio()
    argv = sys.argv[1:]
    explicit = tc.pop_project_arg(argv)
    cmd = argv[0] if argv else ""
    data = {}
    if cmd in ("start", "end", "check"):
        try:
            raw = sys.stdin.buffer.read()
            data = json.loads(raw.decode("utf-8", "replace")) if raw.strip() else {}
        except Exception:
            data = {}
    try:
        root = tc.find_root(explicit, data.get("cwd"))
        if root is None:
            if cmd == "show":
                print("[SESSIONS] no tower.json here; this project has not opted in.")
            sys.exit(0)
        ROOT, CFG = root, tc.load(root)
        if cmd == "start":
            cmd_start(data)
        elif cmd == "end":
            cmd_end(data)
        elif cmd == "check":
            cmd_check(data)
        elif cmd == "show":
            _, rows, _ = load()
            print("\n".join(render(rows, "")) if rows else "[SESSIONS] empty table.")
        else:
            print(__doc__)
    except SystemExit:
        raise
    except Exception as e:  # fail open
        sys.stderr.write(f"[SESSIONS] hook error ignored: {e!r}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
