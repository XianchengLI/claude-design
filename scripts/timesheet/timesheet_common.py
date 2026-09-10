"""Shared configuration for the timesheet tools (timesheet_clock / timesheet_audit / timesheet_report).

A project opts in by keeping `timesheet.json` at its root (see timesheet.example.json and README.md).
Every tool locates the project by, in order: `--project PATH`, `$TIMESHEET_PROJECT`, then walking up
from the current directory. No config means the project does not keep a timesheet: the tools say so
and exit with code 3, so a user-level skill can stop cleanly.
"""
import json
import os
import re
import sys

CONFIG_NAME = "timesheet.json"
NO_CONFIG_EXIT = 3
ROW_RX = re.compile(r"^\| (\d{4}-\d{2}-\d{2}) ")
TABLE_HEAD = "| 日期 | 分类 | 任务 | 交付 / 成果 | 参与人 | 工时(h) | 来源 | 状态 |"
TABLE_SEP = "|---|---|---|---|---|---|---|---|"
PROJECTS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects")

DEFAULTS = {
    "project": "",                       # display name; default = root folder name
    "ledger": "notes/工时记录.md",        # internal ledger (three-layer structure, see README)
    "state": "notes/.clock.json",         # open-clock state file
    "external_ledger": "notes/工时记录_对外.md",
    "external_csv": "",                   # regenerate with `timesheet_report.py --csv`; "" = none
    "external_prefix": "",                # first cell of task rows in the external table; "" = no external page
    "person": "显铖",                     # 参与人 written by clock / draft rows
    "categories": [],                     # ledger vocabulary: what /clock-out may write in 分类
    "report_categories": [],              # chart slots in fixed order (<= 8); default = categories
    "fold": {},                           # ledger category -> chart slot
    "fallback_category": "",              # unknown chart category goes here; default = last report category
    "exclude_categories": ["其他项目"],   # rows excluded from totals and charts
    "milestones": [],                     # [["YYYY-MM-DD", "label"], ...] on the cumulative chart
    "claim_round": 0,                     # suggested claim (h) on the tier chart; 0 = not prepared
    "report_title": "工时报表",
    "report_title_external": "工时报表",
    "report_out": "notes/timesheet_report",
    "keywords": "",                       # regex; blocks in --extra transcript dirs must mention it
    "transcript_dirs": [],                # names under ~/.claude/projects; default = derived from root
    "round_hours": 0.5,                   # 进一法 to this many hours
    "gap_minutes": 30,                    # audit: a longer silence closes a work block
    "pad_minutes": 5,                     # audit: start-up allowance per block
    "skip_dirs": [],                      # extra directory basenames ignored by --window file listing
    "uplift": [0.25, 0.35],               # tier-C low/high multipliers on logged hours
}


def utf8_stdio():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def slug_candidates(root):
    """Claude Code names a project's transcript dir after its path; the drive-letter case and the
    treatment of spaces have varied between versions, so return every plausible spelling."""
    base = os.path.abspath(root).replace(":", "-").replace("\\", "-").replace("/", "-")
    out = set()
    for v in (base, base.replace(" ", "-")):
        out.add(v)
        out.add(v[0].lower() + v[1:])
        out.add(v[0].upper() + v[1:])
    return sorted(out)


def find_project(explicit=None):
    for c in (explicit, os.environ.get("TIMESHEET_PROJECT")):
        if not c:
            continue
        c = os.path.abspath(os.path.expanduser(c))
        if os.path.basename(c) == CONFIG_NAME:
            c = os.path.dirname(c)
        if os.path.isfile(os.path.join(c, CONFIG_NAME)):
            return c
        print(f"[timesheet] {c} 下没有 {CONFIG_NAME}。", file=sys.stderr)
        sys.exit(NO_CONFIG_EXIT)
    d = os.getcwd()
    while True:
        if os.path.isfile(os.path.join(d, CONFIG_NAME)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load(explicit=None):
    """Return the merged config with absolute paths, or exit 3 when the project keeps no timesheet."""
    root = find_project(explicit)
    if root is None:
        print(f"[timesheet] 当前目录 {os.getcwd()} 及其上级没有 {CONFIG_NAME}：本项目不记工时。", file=sys.stderr)
        sys.exit(NO_CONFIG_EXIT)
    with open(os.path.join(root, CONFIG_NAME), encoding="utf-8") as fh:
        raw = json.load(fh)
    unknown = sorted(set(raw) - set(DEFAULTS))
    if unknown:
        print(f"[timesheet] {CONFIG_NAME} 里有未知键，已忽略：{', '.join(unknown)}", file=sys.stderr)
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if k in DEFAULTS})
    cfg["root"] = root
    cfg["project"] = cfg["project"] or os.path.basename(root)
    for k in ("ledger", "state", "external_ledger", "external_csv", "report_out"):
        if cfg[k]:
            cfg[k] = os.path.normpath(os.path.join(root, cfg[k]))
    if not cfg["report_categories"]:
        cfg["report_categories"] = list(cfg["categories"])
    if not cfg["fallback_category"] and cfg["report_categories"]:
        cfg["fallback_category"] = cfg["report_categories"][-1]
    if not cfg["transcript_dirs"]:
        cfg["transcript_dirs"] = slug_candidates(root)
    return cfg


def transcript_dirs(cfg):
    """Existing transcript directories for this project (absolute paths, de-duplicated: on a
    case-insensitive filesystem the upper- and lower-case drive-letter spellings are one folder)."""
    try:
        actual = {os.path.normcase(n): n for n in os.listdir(PROJECTS_DIR)}  # spelling as it exists on disk
    except OSError:
        return []
    out, seen = [], set()
    for n in cfg["transcript_dirs"]:
        real = actual.get(os.path.normcase(n))
        if real is None or real in seen:
            continue
        p = os.path.join(PROJECTS_DIR, real)
        if os.path.isdir(p):
            seen.add(real)
            out.append(p)
    return out


def rel(cfg, path):
    return os.path.relpath(path, cfg["root"]).replace("\\", "/")


def add_project_arg(parser):
    parser.add_argument("--project", help=f"project root (folder holding {CONFIG_NAME}); default: $TIMESHEET_PROJECT or walk up from cwd")
