"""Draft timesheet rows from Claude Code session transcripts, or list what every session did in a window.

Reads every *.jsonl transcript of the project (its dirs under ~/.claude/projects are derived from the
project path, or listed in timesheet.json "transcript_dirs"; add more with --extra), clusters
timestamped events into work blocks, applies the rounding rule (round UP per block), and prints
(a) a per-day audit and (b) draft rows for the ledger.

Usage (any directory inside the project, or --project DIR):
    python timesheet_audit.py                          # everything
    python timesheet_audit.py --since 2026-08-21 --rows
    python timesheet_audit.py --gap 30 --pad 5 --round 0.5
    python timesheet_audit.py --extra "c--Users-Xianc-Documents-The-Vault"      # keep blocks matching "keywords"
    python timesheet_audit.py --status                 # one line if the ledger has unarchived days
    python timesheet_audit.py --draft                  # write those days into the ledger's draft section
    python timesheet_audit.py --window "2026-09-06 11:00-14:30"   # what every session did in one clocked block

Rules:
  * a gap > --gap minutes between consecutive events closes a block
  * each block gets --pad minutes of start-up allowance, then is rounded UP to a multiple of --round hours
  * blocks with zero user messages (session-open pings) are dropped
  * only time spent with the assistant is captured; meetings, reading and hand edits go into the ledger by hand
"""
import argparse
import collections
import datetime as dt
import glob
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timesheet_common as tc  # noqa: E402

tc.utf8_stdio()

DRAFT_START = "<!-- draft:start -->"
DRAFT_END = "<!-- draft:end -->"
BASE_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".claude", "data"}
NOISE_PREFIXES = ("<", "This session is being continued")


def ledger_dates(path):
    """Dates already archived in the 逐日日志 table (draft rows excluded)."""
    dates, in_draft = set(), False
    if not os.path.exists(path):
        return dates
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(DRAFT_START):
                in_draft = True
            elif line.startswith(DRAFT_END):
                in_draft = False
            elif not in_draft and tc.ROW_RX.match(line):
                dates.add(dt.date.fromisoformat(line[2:12]))
    return dates


def write_draft(cfg, perday):
    """Replace the draft section (created before '## 汇总' if missing) with rows for unarchived days."""
    path = cfg["ledger"]
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    lines = [tc.TABLE_HEAD, tc.TABLE_SEP]
    for d, bl in perday.items():
        h = sum(b["hours"] for b in bl)
        spans = ", ".join(f"{b['start']:%H:%M}-{b['end']:%H:%M}" for b in bl)
        hint = " / ".join(b["first"][:40] for b in bl if b["first"])
        lines.append(f"| {d} |  | {hint} |  | {cfg['person']} | {h:.1f} | 日志 {spans} | 草稿 |")
    body = "\n".join(lines) if perday else "（无待归档草稿）"
    block = f"{DRAFT_START}\n## 待归档草稿（脚本自动生成，运行 /timesheet 归档）\n\n{body}\n{DRAFT_END}"
    if DRAFT_START in s and DRAFT_END in s:
        a, b = s.index(DRAFT_START), s.index(DRAFT_END) + len(DRAFT_END)
        s = s[:a] + block + s[b:]
    elif "## 汇总" in s:
        s = s.replace("## 汇总", block + "\n\n## 汇总", 1)
    else:
        s = s.rstrip("\n") + "\n\n" + block + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s)


def load_events(project_dir, kw=None):
    """Return sorted (ts, session, kind, text, hit) events for one transcript dir."""
    events = []
    for f in glob.glob(os.path.join(project_dir, "*.jsonl")):
        sid = os.path.basename(f)[:8]
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                ts = o.get("timestamp")
                if not ts:
                    continue
                t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                kind = o.get("type")
                text = ""
                c = o.get("message", {}).get("content") if isinstance(o.get("message"), dict) else None
                if isinstance(c, str):
                    text = c
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text = part["text"]
                            break
                        if isinstance(part, dict) and part.get("type") == "tool_result" and kind == "user":
                            kind = "tool_result"
                            break
                events.append((t, sid, kind, text))
    events.sort()
    if kw:
        rx = re.compile(kw, re.I)
        return [(t, s, k, x, bool(rx.search(x or ""))) for t, s, k, x in events]
    return [(t, s, k, x, True) for t, s, k, x in events]


def is_noise(text):
    return (not text) or text.startswith(NOISE_PREFIXES)


def make_blocks(events, gap_min, pad_min, round_h):
    gap = dt.timedelta(minutes=gap_min)
    pad = dt.timedelta(minutes=pad_min)
    blocks, cur = [], None
    for t, sid, kind, text, hit in events:
        if cur is None or t - cur["end"] > gap:
            if cur:
                blocks.append(cur)
            cur = {"start": t, "end": t, "n": 0, "user": 0, "hits": 0, "first": "", "sessions": set()}
        cur["end"] = t
        cur["n"] += 1
        cur["hits"] += int(hit)
        cur["sessions"].add(sid)
        if kind == "user" and not is_noise(text):
            cur["user"] += 1
            if not cur["first"]:
                cur["first"] = text[:70].replace("\n", " ")
    if cur:
        blocks.append(cur)
    for b in blocks:
        raw = (b["end"] - b["start"] + pad).total_seconds() / 3600
        b["raw"] = raw
        b["hours"] = math.ceil(raw / round_h) * round_h
    return blocks


def parse_window(spec):
    """'YYYY-MM-DD HH:MM-HH:MM' -> (start, end) as aware local datetimes."""
    day, span = spec.split()
    lo, hi = span.split("-")
    d = dt.date.fromisoformat(day)
    mk = lambda hm: dt.datetime.combine(d, dt.time(*map(int, hm.split(":")))).astimezone()  # noqa: E731
    return mk(lo), mk(hi)


def touched_files(cfg, start, end):
    """Project files whose mtime falls inside the window (data/, caches and configured dirs skipped)."""
    root = cfg["root"]
    skip = BASE_SKIP_DIRS | set(cfg["skip_dirs"])
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                m = dt.datetime.fromtimestamp(os.path.getmtime(fp)).astimezone()
            except OSError:
                continue
            if start <= m <= end:
                out.append((m, os.path.relpath(fp, root).replace("\\", "/")))
    return sorted(out)


def report_window(cfg, spec, dirs):
    """Print what every session did inside one clocked block, plus files touched.

    Feeds /clock-out: one clock block stays ONE ledger row, but that row's 任务/成果
    must cover every session that ran in the window, including ones the archiving
    session cannot see. Read-only; never writes to the ledger.
    """
    start, end = parse_window(spec)
    per = collections.OrderedDict()
    for pdir, kw in dirs:
        for t, sid, kind, text, hit in load_events(pdir, kw):
            if not (start <= t <= end):
                continue
            rec = per.setdefault(sid, {"first": t, "last": t, "msgs": []})
            rec["last"] = t
            if kind == "user" and not is_noise(text):
                rec["msgs"].append((t, " ".join(text.split())[:90]))
    print(f"[window] {spec} · {len(per)} 个 session 活跃")
    for sid, rec in sorted(per.items(), key=lambda kv: kv[1]["first"]):
        print()
        print(f"  {sid}  {rec['first']:%H:%M}-{rec['last']:%H:%M}  用户消息 {len(rec['msgs'])}")
        for t, m in rec["msgs"]:
            print(f"    {t:%H:%M} {m}")
    files = touched_files(cfg, start, end)
    print()
    print(f"[files] 窗口内改动的仓库文件（{len(files)}）")
    for m, f in files:
        print(f"  {m:%H:%M} {f}")
    print()
    print("[提示] 一段打卡只记一次工时：把上面所有 session 的工作内容合并写进同一行的 "
          "任务 / 成果，分类填占比最大的那个，不要按内容拆小时。")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    tc.add_project_arg(ap)
    ap.add_argument("--since", help="YYYY-MM-DD, inclusive")
    ap.add_argument("--until", help="YYYY-MM-DD, inclusive")
    ap.add_argument("--gap", type=int, help="minutes; larger gap closes a block (default from config)")
    ap.add_argument("--pad", type=int, help="start-up allowance per block, minutes (default from config)")
    ap.add_argument("--round", type=float, dest="round_h", help="round UP to multiples of this many hours (default from config)")
    ap.add_argument("--extra", action="append", default=[], help="extra transcript dir name under ~/.claude/projects (repeatable)")
    ap.add_argument("--kw", help="regex; for --extra dirs keep only blocks mentioning it (default: config keywords)")
    ap.add_argument("--rows", action="store_true", help="also print draft markdown rows for the ledger")
    ap.add_argument("--draft", action="store_true", help="write rows for days not yet in the ledger into its draft section (idempotent)")
    ap.add_argument("--status", action="store_true", help="print one line if the ledger has unarchived days (SessionStart hook)")
    ap.add_argument("--window", help='"YYYY-MM-DD HH:MM-HH:MM": list what every session did inside one clocked block (read-only, for /clock-out)')
    args = ap.parse_args()
    cfg = tc.load(args.project)
    gap = args.gap if args.gap is not None else cfg["gap_minutes"]
    pad = args.pad if args.pad is not None else cfg["pad_minutes"]
    round_h = args.round_h if args.round_h is not None else cfg["round_hours"]
    kw = args.kw if args.kw is not None else cfg["keywords"]

    own = tc.transcript_dirs(cfg)
    if not own:
        print(f"[skip] 本项目在 {tc.PROJECTS_DIR} 下没有 transcript 目录（候选：{', '.join(cfg['transcript_dirs'])}）", file=sys.stderr)
    dirs = [(d, None) for d in own]
    for name in args.extra:
        pdir = os.path.join(tc.PROJECTS_DIR, name)
        if os.path.isdir(pdir):
            dirs.append((pdir, kw or None))
        else:
            print(f"[skip] {pdir} not found", file=sys.stderr)

    if args.window:
        report_window(cfg, args.window, dirs)
        return 0

    since = dt.date.fromisoformat(args.since) if args.since else None
    until = dt.date.fromisoformat(args.until) if args.until else None
    archived = ledger_dates(cfg["ledger"]) if (args.draft or args.status) else set()
    if (args.draft or args.status) and not since and archived:
        since = min(archived)

    all_blocks = []
    for pdir, pkw in dirs:
        src = "" if pdir in own else os.path.basename(pdir).split("Documents-")[-1]
        for b in make_blocks(load_events(pdir, pkw), gap, pad, round_h):
            b["src"] = src
            if pkw and b["hits"] == 0:
                continue
            if b["user"] == 0:
                continue
            d = b["start"].date()
            if since and d < since:
                continue
            if until and d > until:
                continue
            all_blocks.append(b)
    all_blocks.sort(key=lambda b: b["start"])

    perday = collections.OrderedDict()
    for b in all_blocks:
        perday.setdefault(b["start"].date(), []).append(b)

    if args.draft or args.status:
        pending = collections.OrderedDict((d, bl) for d, bl in perday.items() if d not in archived)
        if args.draft:
            write_draft(cfg, pending)
        if pending:
            days = ", ".join(f"{d:%m-%d}" for d in pending)
            hours = sum(b["hours"] for bl in pending.values() for b in bl)
            print(f"[timesheet] 工时台账有 {len(pending)} 天未归档（{days}，约 {hours:g} h），运行 /timesheet 归档。")
        elif args.draft:
            print("[timesheet] 无待归档工时。")
        return 0

    total = 0.0
    print(f"{'date':10} {'hours':>6}  blocks (start-end raw->rounded  userMsgs  first message)")
    for d, bl in perday.items():
        h = sum(b["hours"] for b in bl)
        total += h
        print(f"{d} {h:6.1f}")
        for b in bl:
            tag = f" [{b['src']}]" if b["src"] else ""
            print(f"      {b['start']:%H:%M}-{b['end']:%H:%M}  {b['raw']:.2f}->{b['hours']:.1f}h  u={b['user']:<3} {b['first']}{tag}")
    print(f"\nTOTAL {total:.1f} h over {len(perday)} days  (gap>{gap}min, pad {pad}min, round up to {round_h}h)")

    if args.rows:
        print(f"\n--- draft rows for {tc.rel(cfg, cfg['ledger'])} (fill 分类/任务/成果 by hand) ---")
        print(tc.TABLE_HEAD)
        print(tc.TABLE_SEP)
        for d, bl in perday.items():
            h = sum(b["hours"] for b in bl)
            spans = ", ".join(f"{b['start']:%H:%M}-{b['end']:%H:%M}" for b in bl)
            hint = bl[0]["first"][:40]
            print(f"| {d} |  | {hint} |  | {cfg['person']} | {h:.1f} | 日志 {spans} | 完成 |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
