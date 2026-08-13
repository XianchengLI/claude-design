"""
Vault health check for The Vault.

Read-only structural audit (no LLM). Detects:
  1. Broken wikilinks       — [[targets]] that resolve to no note in the vault
  2. Status drift           — CLAUDE.md Active Projects whose note + Daily
                              mentions are both older than --stale-days
  3. Orphan notes           — People/ and Ideas/ notes with zero inbound
                              wikilinks from the rest of the vault
  4. Frontmatter compliance — notes missing YAML frontmatter or a `tags` key
                              (writing-rules.md requirement)
  5. Rotation reminder      — CLAUDE.md Recent Activity oldest entry older
                              than --window-days (rolling-window rule)

Usage:
  python .claude/scripts/vault_health.py            # report to stdout
  python .claude/scripts/vault_health.py --write    # also save Tools/Vault-Health-Report.md
  python .claude/scripts/vault_health.py --stale-days 60

Scans all *.md under the vault except: .claude/ .obsidian/ .git/ .trash/
Templates/ Temp/ (Templates hold placeholder links; Temp is not notes).
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
EXCLUDE_DIRS = {".claude", ".obsidian", ".git", ".trash", "Templates", "Temp",
                "scratchpad", "vault-starter-kit"}

WIKILINK_RE = re.compile(r"!?\[\[([^\[\]]+?)\]\]")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
DATE_ENTRY_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2})")
ACTIVE_PROJECT_RE = re.compile(r"^- \*\*\[\[([^\]|#]+)", re.M)
DAILY_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def collect_notes() -> list[Path]:
    notes = []
    for p in VAULT.rglob("*.md"):
        rel = p.relative_to(VAULT)
        if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        notes.append(p)
    return notes


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8-sig")  # -sig: tolerate BOM
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar fields of the YAML frontmatter (cheap parse, no lists)."""
    if not text.startswith("---") or text.count("---") < 2:
        return {}
    fields = {}
    for line in text.split("---", 2)[1].splitlines():
        m = re.match(r"^(\w[\w-]*)\s*:\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def strip_code_blocks(text: str) -> str:
    """Drop fenced blocks and inline code spans so links inside them
    (examples, counter-examples in gotcha notes) are not treated as real."""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


def link_targets(text: str) -> list[str]:
    """Wikilink targets with alias/heading parts stripped."""
    targets = []
    for m in WIKILINK_RE.finditer(text):
        t = m.group(1).split("|")[0].split("#")[0].strip()
        if not t or "{" in t:  # skip empty ([[#h]]) and template placeholders
            continue
        targets.append(t)
    return targets


def build_resolvers(notes: list[Path]):
    """Obsidian resolves by basename (case-insensitive) or vault-relative path."""
    by_name: dict[str, Path] = {}
    by_relpath: dict[str, Path] = {}
    for p in notes:
        by_name.setdefault(p.stem.casefold(), p)
        rel = p.relative_to(VAULT).as_posix()
        by_relpath[rel.casefold()] = p
        by_relpath[rel[: -len(".md")].casefold()] = p
    return by_name, by_relpath


def resolves(target: str, by_name, by_relpath) -> bool:
    t = target.casefold()
    if t in by_name or t in by_relpath:
        return True
    # non-.md attachment embeds ([[img.png]]) — accept if the file exists anywhere
    if "." in Path(target).name:
        return any(VAULT.rglob(Path(target).name))
    return False


def days_ago(d: date) -> int:
    return (date.today() - d).days


def mtime_date(p: Path) -> date:
    return datetime.fromtimestamp(p.stat().st_mtime).date()


def main() -> None:
    ap = argparse.ArgumentParser(description="Vault structural health check")
    ap.add_argument("--stale-days", type=int, default=45,
                    help="active project with no touch in N days = drifted (default 45)")
    ap.add_argument("--idea-days", type=int, default=90,
                    help="Ideas/ note untouched for N days = stale seed (default 90)")
    ap.add_argument("--window-days", type=int, default=56,
                    help="Recent Activity entries older than N days should rotate (default 56)")
    ap.add_argument("--write", action="store_true",
                    help="also write Tools/Vault-Health-Report.md")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    notes = collect_notes()
    by_name, by_relpath = build_resolvers(notes)
    texts = {p: read_text(p) for p in notes}
    prose = {p: strip_code_blocks(t) for p, t in texts.items()}

    # ---- 1. broken wikilinks -------------------------------------------------
    broken: list[tuple[str, str]] = []  # (relpath, target)
    for p, t in prose.items():
        for target in link_targets(t):
            if not resolves(target, by_name, by_relpath):
                broken.append((p.relative_to(VAULT).as_posix(), target))

    # ---- inbound-link index (for orphans) -----------------------------------
    inbound: dict[str, int] = {}
    for p, t in prose.items():
        src = p.stem.casefold()
        for target in link_targets(t):
            key = Path(target).stem.casefold()
            if key != src:  # self-links don't count
                inbound[key] = inbound.get(key, 0) + 1

    # ---- 2. status drift -----------------------------------------------------
    claude_md = read_text(VAULT / "CLAUDE.md")
    active = ACTIVE_PROJECT_RE.findall(
        claude_md.split("### Active Projects")[-1].split("### Completed")[0]
    ) if "### Active Projects" in claude_md else []

    # last Daily mention per project (filename date of newest Daily note naming it)
    daily_notes = sorted(
        (p for p in notes if p.parent.name == "Daily" and DAILY_NAME_RE.match(p.name)),
        key=lambda p: p.name, reverse=True,
    )
    drift: list[tuple[str, str, int]] = []   # (project, detail, days)
    missing_note: list[str] = []
    for proj in (x.strip() for x in active):
        note = by_name.get(proj.casefold())
        last: date | None = mtime_date(note) if note else None
        for dp in daily_notes:
            if proj.casefold() in texts[dp].casefold():
                d = date.fromisoformat(DAILY_NAME_RE.match(dp.name).group(1))
                last = max(last, d) if last else d
                break  # newest first — first hit is the latest mention
        if note is None:
            missing_note.append(proj)
        if last is None:
            continue
        if days_ago(last) > args.stale_days:
            where = note.relative_to(VAULT).as_posix() if note else "(no note)"
            drift.append((proj, where, days_ago(last)))
    drift.sort(key=lambda x: -x[2])

    # ---- 3. orphans ----------------------------------------------------------
    # Notes with `status: dormant` in frontmatter are intentionally parked:
    # exempt from orphan/stale checks until their `revisit: YYYY-MM-DD` passes,
    # at which point they surface as "revisit due".
    orphans: list[str] = []
    stale_ideas: list[tuple[str, int]] = []
    revisit_due: list[tuple[str, str]] = []
    dormant_n = 0
    for p in notes:
        if p.parent.name not in {"People", "Ideas"}:
            continue
        rel = p.relative_to(VAULT).as_posix()
        fm = frontmatter(texts[p])
        if "dormant" in fm.get("status", ""):
            dormant_n += 1
            rv = fm.get("revisit", "")
            try:
                if rv and date.fromisoformat(rv) <= date.today():
                    revisit_due.append((rel, rv))
            except ValueError:
                revisit_due.append((rel, f"unparseable revisit: {rv!r}"))
            continue
        if inbound.get(p.stem.casefold(), 0) == 0:
            # People may be referenced via frontmatter `people:` lists instead
            mentioned = any(p.stem in t for q, t in texts.items() if q != p)
            if not mentioned:
                orphans.append(rel)
        if p.parent.name == "Ideas" and days_ago(mtime_date(p)) > args.idea_days:
            stale_ideas.append((rel, days_ago(mtime_date(p))))

    # ---- 4. frontmatter ------------------------------------------------------
    no_fm, no_tags = [], []
    for p in notes:
        t = texts[p]
        rel = p.relative_to(VAULT).as_posix()
        if p.name == "CLAUDE.md":
            continue  # operating manual, not a note
        if not t.startswith("---"):
            no_fm.append(rel)
            continue
        head = t.split("---", 2)[1] if t.count("---") >= 2 else ""
        if not re.search(r"^tags\s*:", head, re.M):
            no_tags.append(rel)

    # ---- 5. rotation reminder ------------------------------------------------
    rotation_due, oldest_days = False, 0
    if "### Recent Activity" in claude_md:
        section = claude_md.split("### Recent Activity")[-1]
        dates = [date.fromisoformat(d) for d in DATE_ENTRY_RE.findall(section)]
        if dates:
            oldest_days = days_ago(min(dates))
            rotation_due = oldest_days > args.window_days

    # ---- report --------------------------------------------------------------
    lines = []
    add = lines.append
    add(f"# Vault Health Report — {date.today().isoformat()}")
    add("")
    add(f"Scanned {len(notes)} notes. Thresholds: stale={args.stale_days}d, "
        f"ideas={args.idea_days}d, window={args.window_days}d.")
    add("")

    add(f"## 1. Broken wikilinks — {len(broken)}")
    for src, target in sorted(broken):
        add(f"- `{src}` → `[[{target}]]`")
    if not broken:
        add("- none ✅")
    add("")

    add(f"## 2. Active-project status drift — {len(drift)} of {len(active)}")
    add(f"_(no note-file edit AND no Daily mention within {args.stale_days} days)_")
    for proj, where, days in drift:
        add(f"- **{proj}** — last touch {days}d ago (`{where}`)")
    if not drift:
        add("- none ✅")
    if missing_note:
        add(f"- ⚠️ listed Active but no note file found: {', '.join(missing_note)}")
    add("")

    add(f"## 3. Orphan notes (People/, Ideas/) — {len(orphans)}")
    for rel in sorted(orphans):
        add(f"- `{rel}` — no inbound link or mention anywhere")
    if not orphans:
        add("- none ✅")
    if stale_ideas:
        add(f"- stale seeds (>{args.idea_days}d untouched): "
            + ", ".join(f"`{r}` ({d}d)" for r, d in sorted(stale_ideas, key=lambda x: -x[1])))
    for rel, rv in revisit_due:
        add(f"- ⏰ dormant note revisit due ({rv}): `{rel}`")
    if dormant_n:
        add(f"- dormant (parked, checks skipped): {dormant_n}")
    add("")

    add(f"## 4. Frontmatter compliance — {len(no_fm)} missing, {len(no_tags)} without tags")
    for rel in sorted(no_fm):
        add(f"- no frontmatter: `{rel}`")
    for rel in sorted(no_tags):
        add(f"- no `tags:` key: `{rel}`")
    if not no_fm and not no_tags:
        add("- all compliant ✅")
    add("")

    add("## 5. Recent Activity rolling window")
    if rotation_due:
        add(f"- ⚠️ oldest entry is {oldest_days}d old (>{args.window_days}d) — "
            "rotate to `Sessions/Activity-Archive.md`")
    else:
        add(f"- within window (oldest entry {oldest_days}d old) ✅")

    report = "\n".join(lines) + "\n"
    print(report)

    if args.write:
        out = VAULT / "Tools" / "Vault-Health-Report.md"
        out.write_text(
            "---\ntags: [tool, report, vault-health]\n---\n\n" + report,
            encoding="utf-8",
        )
        print(f"[written] {out}")


if __name__ == "__main__":
    main()
