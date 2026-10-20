#!/usr/bin/env python3
"""Install / check / remove the multi-session tower kit in a project.

  python tower_init.py init   --project DIR --level 2|3 [--code-repo REL_OR_ABS ...]
  python tower_init.py doctor --project DIR      (or: doctor --all)
  python tower_init.py unlink --project DIR

init (idempotent, safe to re-run after editing the kit or tower.json):
  1. tower.json            created from templates/tower.example.json if missing (never overwritten)
  2. canonical files       created from templates if missing (never overwritten)
  3. rules                 templates/claude_md_snippet*.md rendered to <root>/.claude/tower-rules.md (regenerated),
                           imported from CLAUDE.local.md as `@./.claude/tower-rules.md`
                           (@-imports only load real repo-relative paths; ~/ or absolute paths are silently ignored)
  4. skills                junctions <root>/.claude/skills/<name> -> claude-design/skills/tower/<name>
                           L2: task-close, judge-bundle, judge-bundle-run   L3: + tower-in, tower-out
  5. hooks                 SessionStart / SessionEnd / PreToolUse entries merged into <root>/.claude/settings.local.json
  6. git hygiene           SESSIONS table, tower-rules copy, CLAUDE.local.md and skill junctions go to .git/info/exclude
                           (written without BOM; a BOM turns line 1 into a pattern)
  7. registry              project path appended to linked-projects.txt
Level 1 needs no kit: use /wrap + MEMORY.md.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tower_common as tc  # noqa: E402

KIT = tc.KIT
TEMPLATES = KIT / "templates"
SKILLS_SRC = KIT.parent.parent / "skills" / "tower"
REGISTRY = KIT / "linked-projects.txt"
HOOK = KIT / "sessions_hook.py"
SKILLS = {2: ["task-close", "judge-bundle", "judge-bundle-run"], 3: ["task-close", "judge-bundle", "judge-bundle-run", "tower-in", "tower-out"]}
FILES = {2: ["tasks", "decisions", "gotchas", "inbox"], 3: ["tasks", "decisions", "gotchas", "inbox", "handover", "tower_log"]}
TEMPLATE_OF = {"tasks": "tasks.md", "decisions": "decisions.md", "gotchas": "gotchas.md", "inbox": "CLAUDE_inbox.md",
               "handover": "handover.md", "tower_log": "tower_log.md"}
RULES_REL = ".claude/tower-rules.md"
IMPORT_LINE = "@./.claude/tower-rules.md"
MARK = "tower" + os.sep + "sessions_hook.py"


def say(tag, msg):
    print(f"  [{tag}] {msg}")


def write_text(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def render_rules(root: Path, cfg: dict) -> str:
    lv = int(cfg["level"])
    body = (TEMPLATES / "claude_md_snippet.md").read_text(encoding="utf-8")
    l3 = (TEMPLATES / "claude_md_snippet_L3.md").read_text(encoding="utf-8") if lv >= 3 else ""
    body = body.replace("<L3>", l3)
    f, lim = cfg["files"], cfg["limits"]
    subs = {
        "<LEVEL>": str(lv), "<BUDGET>": f"{lim['claude_md_chars']:,}", "<MEMORY>": f["memory"], "<SESSIONS>": f["sessions"],
        "<TASKS>": f["tasks"], "<DECISIONS>": f["decisions"], "<GOTCHAS>": f["gotchas"], "<INBOX>": f["inbox"],
        "<HANDOVER>": f["handover"], "<TOWERLOG>": f["tower_log"], "<DOING>": cfg["task_sections"]["doing"],
        "<CARD>": str(lim["start_card_minutes"]), "<SOFT>": str(lim["ctx_soft_k"]), "<HARD>": str(lim["ctx_hard_k"]),
        "<MAXW>": str(lim["max_workers"]), "<MAXH>": str(lim["max_heavy"]),
        "<SHARED>": ", ".join(f"`{s}`" for s in cfg["shared_files"]) or "MEMORY, task list, decisions, gotchas",
        "<KIT>": str(KIT).replace("\\", "/"),
    }
    for k, v in subs.items():
        body = body.replace(k, v)
    return body


def is_junction(p: Path) -> bool:
    try:
        return p.is_symlink() or bool(os.readlink(p))
    except (OSError, ValueError):
        return False


def link(src: Path, dst: Path):
    if dst.exists() or is_junction(dst):
        if is_junction(dst):
            return "ok"
        return "exists-not-link"
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], capture_output=True, text=True)
    return "linked" if r.returncode == 0 else f"failed: {r.stderr.strip() or r.stdout.strip()}"


def hook_cmd(root: Path, sub: str) -> str:
    return f'python "{HOOK}" --project "{root}" {sub}'


def merge_hooks(root: Path) -> str:
    sp = root / ".claude" / "settings.local.json"
    data = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    hooks = data.setdefault("hooks", {})
    wanted = {
        "SessionStart": ({"matcher": "*"}, "start"),
        "SessionEnd": ({}, "end"),
        "PreToolUse": ({"matcher": "Edit|Write|MultiEdit"}, "check"),
    }
    changed = False
    for event, (extra, sub) in wanted.items():
        groups = hooks.setdefault(event, [])
        present = any(MARK in h.get("command", "") for g in groups for h in g.get("hooks", []))
        if not present:
            groups.append({**extra, "hooks": [{"type": "command", "command": hook_cmd(root, sub), "timeout": 10}]})
            changed = True
    if changed:
        write_text(sp, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return "merged"
    return "ok"


def remove_hooks(root: Path):
    sp = root / ".claude" / "settings.local.json"
    if not sp.exists():
        return
    data = json.loads(sp.read_text(encoding="utf-8"))
    for event, groups in list(data.get("hooks", {}).items()):
        kept = []
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if MARK not in h.get("command", "")]
            if g["hooks"]:
                kept.append(g)
        data["hooks"][event] = kept
        if not kept:
            del data["hooks"][event]
    write_text(sp, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def ensure_import(root: Path) -> str:
    p = root / "CLAUDE.local.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    if IMPORT_LINE in text.splitlines():
        return "ok"
    text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + IMPORT_LINE + "\n"
    write_text(p, text)
    return "added"


def exclude(root: Path, entries: list[str]) -> str:
    ex = root / ".git" / "info" / "exclude"
    if not (root / ".git").is_dir():
        return "no .git (skipped)"
    have = ex.read_text(encoding="utf-8-sig").splitlines() if ex.exists() else []
    add = [e for e in entries if e not in have]
    if add:
        write_text(ex, "\n".join(have + ["# tower kit"] * (not any("tower kit" in h for h in have)) + add) + "\n")
    return f"+{len(add)}" if add else "ok"


def register(root: Path):
    have = REGISTRY.read_text(encoding="utf-8").splitlines() if REGISTRY.exists() else []
    if str(root) not in have:
        write_text(REGISTRY, "\n".join(have + [str(root)]) + "\n")


def cmd_init(a):
    root = Path(a.project).resolve()
    print(f"init {root}")
    cfg_path = root / tc.CONFIG_NAME
    if not cfg_path.exists():
        cfg = json.loads((TEMPLATES / "tower.example.json").read_text(encoding="utf-8"))
        cfg["project"] = root.name
        cfg["level"] = a.level or 2
        cfg["code_repos"] = a.code_repo or []
        write_text(cfg_path, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        say("config", f"tower.json created (level {cfg['level']})")
    else:
        say("config", "tower.json exists, kept" + (" (--level ignored: edit tower.json)" if a.level else ""))
    cfg = tc.load(root)
    lv = int(cfg["level"])
    if lv < 2:
        say("level", "level 1 needs no kit: use /wrap + MEMORY.md. Nothing else installed.")
        return
    for key in FILES[3 if lv >= 3 else 2]:
        p = tc.path(root, cfg, key)
        if p.exists():
            say("file", f"{cfg['files'][key]} exists, kept")
        else:
            write_text(p, (TEMPLATES / TEMPLATE_OF[key]).read_text(encoding="utf-8"))
            say("file", f"{cfg['files'][key]} created")
    mem = tc.path(root, cfg, "memory")
    if not mem.exists():
        write_text(mem, "# MEMORY · current state (≤ 40 lines, one line per workstream: state + evidence + next step)\n")
        say("file", f"{cfg['files']['memory']} created")
    write_text(root / RULES_REL, render_rules(root, cfg))
    say("rules", f"{RULES_REL} regenerated; CLAUDE.local.md import {ensure_import(root)}")
    names = SKILLS[3 if lv >= 3 else 2]
    for n in names:
        say("skill", f"{n}: {link(SKILLS_SRC / n, root / '.claude' / 'skills' / n)}")
    say("hooks", merge_hooks(root))
    ex = [cfg["files"]["sessions"], RULES_REL, "CLAUDE.local.md"] + [f".claude/skills/{n}" for n in names]
    say("git", f".git/info/exclude {exclude(root, ex)}")
    register(root)
    say("next", "open a new session: the SessionStart hook registers it; CLAUDE.md stays yours.")


def cmd_doctor(a):
    roots = [Path(l) for l in REGISTRY.read_text(encoding="utf-8").splitlines() if l.strip()] if a.all else [Path(a.project).resolve()]
    for root in roots:
        print(root)
        if not (root / tc.CONFIG_NAME).exists():
            say("config", "MISSING tower.json")
            continue
        cfg = tc.load(root)
        lv = int(cfg["level"])
        rules = root / RULES_REL
        say("rules", "ok" if rules.exists() and rules.read_text(encoding="utf-8") == render_rules(root, cfg)
            else "STALE or missing: re-run init")
        lp = root / "CLAUDE.local.md"
        say("import", "ok" if lp.exists() and IMPORT_LINE in lp.read_text(encoding="utf-8").splitlines() else "MISSING")
        for n in SKILLS[3 if lv >= 3 else 2]:
            d = root / ".claude" / "skills" / n
            say("skill", f"{n}: " + ("ok" if is_junction(d) and (d / "SKILL.md").exists() else "BROKEN or missing"))
        sp = root / ".claude" / "settings.local.json"
        n_hooks = sp.read_text(encoding="utf-8").count("sessions_hook.py") if sp.exists() else 0
        say("hooks", "ok" if n_hooks >= 3 else f"only {n_hooks}/3")
        cm = tc.path(root, cfg, "claude_md")
        if cm.exists():
            n = len(cm.read_text(encoding="utf-8"))
            cap = cfg["limits"]["claude_md_chars"]
            say("budget", f"CLAUDE.md {n:,} / {cap:,} chars" + ("  OVER" if n > cap else ""))


def cmd_unlink(a):
    root = Path(a.project).resolve()
    print(f"unlink {root}")
    for n in SKILLS[3]:
        d = root / ".claude" / "skills" / n
        if is_junction(d):
            os.rmdir(d)  # removes the junction only, never the kit
            say("skill", f"{n} unlinked")
    remove_hooks(root)
    say("hooks", "removed")
    lp = root / "CLAUDE.local.md"
    if lp.exists():
        lines = [l for l in lp.read_text(encoding="utf-8").splitlines() if l.strip() != IMPORT_LINE]
        write_text(lp, "\n".join(lines).strip() + "\n") if any(l.strip() for l in lines) else lp.unlink()
    r = root / RULES_REL
    if r.exists():
        r.unlink()
    say("rules", "import and copy removed; tower.json and notes files kept")
    if REGISTRY.exists():
        keep = [l for l in REGISTRY.read_text(encoding="utf-8").splitlines() if l.strip() and Path(l).resolve() != root]
        write_text(REGISTRY, "\n".join(keep) + ("\n" if keep else ""))


def main():
    tc.utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "doctor", "unlink"])
    ap.add_argument("--project", default=".")
    ap.add_argument("--level", type=int, choices=[1, 2, 3])
    ap.add_argument("--code-repo", action="append")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    {"init": cmd_init, "doctor": cmd_doctor, "unlink": cmd_unlink}[a.cmd](a)


if __name__ == "__main__":
    main()
