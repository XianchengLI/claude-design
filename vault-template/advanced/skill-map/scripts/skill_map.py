"""
Skill map generator for a personal vault (Obsidian + Claude Code).

Scans every location where Claude Code skills/commands live and generates
one note per skill under Skills/, plus category hub notes under
Skills/Categories/ and the Skills/Skill-Map.md entry point. The Obsidian
graph then renders each category hub as a large node with its skills
arranged around it (node size scales with link count).

Scanned sources:
  1. Global skills    ~/.claude/skills/*/SKILL.md
  2. Global commands  ~/.claude/commands/*.md
  3. Project skills   <projects_root>/*/.claude/skills/*/SKILL.md
     Project commands <projects_root>/*/.claude/commands/*.md
  4. Plugin skills    installPath/skills/*/SKILL.md + installPath/commands/*.md
     for plugins marked true in ~/.claude/settings.json enabledPlugins
     (name prefixed "<plugin>:<skill>", matching how sessions surface them)

Two-layer notes: everything ABOVE the "%% MANUAL %%" marker is machine-owned
and regenerated on every run; everything from the marker down is human-owned
and always preserved. Notes whose skill disappeared from disk get
status: removed (never deleted automatically).

Category assignment lives in skill_map_config.json (categories block).
Skills not listed there land in the "Uncategorized" hub and are reported.

Usage:
  python .claude/scripts/skill_map.py            # generate/update + report
  python .claude/scripts/skill_map.py --dry-run  # report only, write nothing
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
SKILLS_DIR = VAULT / "Skills"
CAT_DIR = SKILLS_DIR / "Categories"
CONFIG_PATH = Path(__file__).with_name("skill_map_config.json")
HOME = Path.home()
MARKER = "%% MANUAL %%"
# Pages in Skills/ that are not generated leaf notes.
# Entry point is "Skill-Index" (NOT "Skill-Map"): Windows filesystems are
# case-insensitive, so Skill-Map.md would collide with the skill-map.md leaf.
STATIC_PAGES = {"Skill-Index.md", "Built-in-Skills.md"}


# ---------------------------------------------------------------- parsing

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> dict[str, str]:
    """YAML frontmatter, tolerating multi-line folded values (indented
    continuation lines are appended to the previous key)."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fields: dict[str, str] = {}
    current = None
    for line in parts[1].splitlines():
        m = re.match(r"^(\w[\w-]*)\s*:\s*(.*)$", line)
        if m:
            current = m.group(1)
            val = m.group(2).strip()
            # strip YAML block-scalar markers (>, >-, |, |-)
            fields[current] = "" if val in {">", ">-", "|", "|-"} else val
        elif current and line[:1].isspace() and line.strip():
            fields[current] = (fields[current] + " " + line.strip()).strip()
    return fields


def command_description(text: str) -> str:
    """Commands often have no frontmatter: fall back to the first paragraph
    of prose after the leading heading."""
    fm = parse_frontmatter(text)
    if fm.get("description"):
        return fm["description"]
    body = text.split("---", 2)[2] if text.startswith("---") and text.count("---") >= 2 else text
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if para and not para.startswith("#"):
            return re.sub(r"\s+", " ", para)
    return "(no description found)"


# ---------------------------------------------------------------- scanning

def scan(cfg: dict) -> dict[str, dict]:
    """Return {skill_name: record}. Records merge duplicates across scopes
    (e.g. the same toolkit skill vendored into two repos)."""
    records: dict[str, dict] = {}

    def add(name: str, kind: str, scope: str, source: Path, desc: str):
        r = records.setdefault(name, {
            "name": name, "kinds": set(), "scopes": [], "sources": [], "description": ""})
        r["kinds"].add(kind)
        if scope not in r["scopes"]:
            r["scopes"].append(scope)
        r["sources"].append(source.as_posix())
        if desc and not r["description"]:
            r["description"] = desc

    def add_skill_dir(skills_dir: Path, scope: str, prefix: str = ""):
        for sk in sorted(skills_dir.glob("*/SKILL.md")):
            fm = parse_frontmatter(read_text(sk))
            # directory name, not frontmatter name: it is what the harness
            # surfaces (e.g. save-progress/ declares name: save)
            name = prefix + sk.parent.name
            add(name, "skill", scope, sk.parent, fm.get("description", ""))

    def add_command_dir(cmd_dir: Path, scope: str, prefix: str = ""):
        for cmd in sorted(cmd_dir.glob("*.md")):
            name = prefix + cmd.stem
            add(name, "command", scope, cmd, command_description(read_text(cmd)))

    # 1-2. global
    add_skill_dir(HOME / ".claude" / "skills", "global")
    add_command_dir(HOME / ".claude" / "commands", "global")

    # 3. projects
    root = Path(cfg["projects_root"])
    vault_name = cfg.get("vault_folder_name", "")
    if root.is_dir():
        for proj in sorted(root.iterdir()):
            claude_dir = proj / ".claude"
            if not claude_dir.is_dir():
                continue
            scope = "vault" if proj.name == vault_name else f"project:{proj.name}"
            add_skill_dir(claude_dir / "skills", scope)
            add_command_dir(claude_dir / "commands", scope)

    # 4. enabled plugins
    try:
        settings = json.loads(read_text(HOME / ".claude" / "settings.json"))
        installed = json.loads(read_text(HOME / ".claude" / "plugins" / "installed_plugins.json"))
        enabled = {k for k, v in settings.get("enabledPlugins", {}).items() if v}
        for full_name, installs in installed.get("plugins", {}).items():
            if full_name not in enabled or not installs:
                continue
            plugin = full_name.split("@")[0]
            install_path = Path(installs[0]["installPath"])
            add_skill_dir(install_path / "skills", f"plugin:{plugin}", prefix=f"{plugin}:")
            add_command_dir(install_path / "commands", f"plugin:{plugin}", prefix=f"{plugin}:")
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"  [warn] plugin scan skipped: {e}")

    return records


# ---------------------------------------------------------------- rendering

def note_filename(name: str) -> str:
    return name.replace(":", "-") + ".md"


def invocation(rec: dict) -> str:
    slash = f"/{rec['name']}"
    if "skill" in rec["kinds"]:
        return f"auto (description match) or {slash}"
    return f"{slash} (explicit only)"


def render_leaf(rec: dict, category: str) -> str:
    kind = "+".join(sorted(rec["kinds"]))
    scopes = ", ".join(rec["scopes"])
    sources = "; ".join(rec["sources"])
    desc = rec["description"] or "(no description)"
    return (
        "---\n"
        # nested tag skill/<category> lets Obsidian graph color-groups
        # color leaves per category (tag matching is reliable in the graph
        # search; frontmatter-property matching is not)
        f"tags: [skill, skill/{category.lower()}]\n"
        f"skill-name: {rec['name']}\n"
        f"kind: {kind}\n"
        f"scope: {scopes}\n"
        f"category: {category}\n"
        f"invocation: \"{invocation(rec)}\"\n"
        f"status: active\n"
        f"source: \"{sources}\"\n"
        "---\n\n"
        f"# {rec['name']}\n\n"
        f"**Description**: {desc}\n\n"
        f"{MARKER}"
    )


def short_desc(desc: str, limit: int = 140) -> str:
    desc = re.sub(r"\s+", " ", desc).strip()
    # first sentence if it is reasonably short, else hard truncate
    m = re.match(r"(.{20,%d}?[.。])\s" % limit, desc)
    if m:
        return m.group(1)
    return desc[:limit].rstrip() + ("…" if len(desc) > limit else "")


def render_hub(category: str, members: list[dict]) -> str:
    lines = [
        "---",
        "tags: [moc]",
        "---",
        "",
        f"# {category}",
        "",
    ]
    for rec in members:
        link = note_filename(rec["name"])[:-3]
        alias = f"|{rec['name']}" if link != rec["name"] else ""
        lines.append(f"- [[{link}{alias}]] — {short_desc(rec['description'])}")
    lines += ["", MARKER]
    return "\n".join(lines)


def render_map(categories: list[str], counts: dict[str, int]) -> str:
    lines = [
        "---",
        "tags: [moc]",
        "---",
        "",
        "# Skill Index",
        "",
        "Entry point for the skill inventory. Generated by "
        "`.claude/scripts/skill_map.py`; regenerate after installing or "
        "removing skills (or run /skill-map).",
        "",
        "## Categories",
        "",
    ]
    for cat in categories:
        lines.append(f"- [[{cat}]] ({counts[cat]})")
    lines += [
        "",
        "## Built-ins",
        "",
        "- [[Built-in-Skills]] — harness-provided skills (not user-managed, "
        "kept off the graph as leaf notes)",
        "",
        MARKER,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- writing

def write_note(path: Path, machine_text: str, default_manual: str,
               dry: bool) -> str:
    """Regenerate the machine layer, preserve the manual layer. Returns
    'created' | 'updated' | 'unchanged' | 'skipped-no-marker'."""
    if path.exists():
        old = read_text(path)
        if MARKER in old:
            manual = old.split(MARKER, 1)[1]
        else:
            return "skipped-no-marker"
        new = machine_text + manual
        if new == old:
            return "unchanged"
        if not dry:
            path.write_text(new, encoding="utf-8", newline="\n")
        return "updated"
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(machine_text + default_manual, encoding="utf-8", newline="\n")
    return "created"


def mark_removed(path: Path, dry: bool) -> bool:
    text = read_text(path)
    if re.search(r"^status: removed$", text, re.M):
        return False
    new = re.sub(r"^status: active$", "status: removed", text, count=1, flags=re.M)
    if new != text:
        if not dry:
            path.write_text(new, encoding="utf-8", newline="\n")
        return True
    return False


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Skills/ notes from installed skills")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()
    dry = args.dry_run

    cfg = json.loads(read_text(CONFIG_PATH))
    cat_of = {name: cat for cat, names in cfg["categories"].items() for name in names}

    records = scan(cfg)
    print(f"Scanned: {len(records)} skills/commands")

    # leaves
    stats: dict[str, list[str]] = {}
    uncategorized = []
    by_category: dict[str, list[dict]] = {}
    for name, rec in sorted(records.items()):
        cat = cat_of.get(name)
        if cat is None:
            cat = "Uncategorized"
            uncategorized.append(name)
        by_category.setdefault(cat, []).append(rec)
        result = write_note(SKILLS_DIR / note_filename(name), render_leaf(rec, cat),
                            "\n\n## Notes\n\n", dry)
        stats.setdefault(result, []).append(name)

    # hubs
    cats = sorted(by_category)
    for cat in cats:
        result = write_note(CAT_DIR / f"{cat}.md", render_hub(cat, by_category[cat]),
                            "\n\n## Notes\n\n", dry)
        stats.setdefault(result, []).append(f"[hub] {cat}")

    # map
    counts = {c: len(m) for c, m in by_category.items()}
    result = write_note(SKILLS_DIR / "Skill-Index.md", render_map(cats, counts),
                        "\n\n## Notes\n\n", dry)
    stats.setdefault(result, []).append("[index] Skill-Index")

    # removed detection
    known_files = {note_filename(n) for n in records} | STATIC_PAGES
    removed = []
    if SKILLS_DIR.is_dir():
        for p in sorted(SKILLS_DIR.glob("*.md")):
            if p.name not in known_files and mark_removed(p, dry):
                removed.append(p.name)

    # config entries that no longer exist on disk
    ghost_cfg = sorted(set(cat_of) - set(records))

    # report
    print()
    for key in ("created", "updated", "unchanged", "skipped-no-marker"):
        if key in stats:
            names = stats[key]
            detail = ", ".join(names) if key in ("created", "updated", "skipped-no-marker") else str(len(names))
            print(f"  {key:18s} {len(names):3d}  {detail if key != 'unchanged' else ''}".rstrip())
    if uncategorized:
        print(f"\n  UNCATEGORIZED ({len(uncategorized)}): {', '.join(uncategorized)}")
        print("  -> assign them in skill_map_config.json categories block")
    if removed:
        print(f"\n  MARKED REMOVED: {', '.join(removed)} (note kept; delete manually if confirmed)")
    if ghost_cfg:
        print(f"\n  IN CONFIG BUT NOT ON DISK: {', '.join(ghost_cfg)}")
    if dry:
        print("\n  (dry run — nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
