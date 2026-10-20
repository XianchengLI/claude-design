"""Manual clock-in / clock-out for a project's timesheet ledger.

    python timesheet_clock.py [--project DIR] start  [--note "..."] [--at HH:MM]
    python timesheet_clock.py [--project DIR] stop   [--note "..."] [--cat 分类] [--result "..."] [--at HH:MM] [--start HH:MM] [--deduct MIN]
    python timesheet_clock.py [--project DIR] break  --minutes N [--note "..."]   # unrelated interruption; deducted at stop
    python timesheet_clock.py [--project DIR] note   [--cat 分类] [--note "..."] [--result "..."] [--session ID]
    python timesheet_clock.py [--project DIR] status         # one line if a clock is open, else nothing (SessionStart hook)
    python timesheet_clock.py [--project DIR] cancel         # discard the open clock
    python timesheet_clock.py [--project DIR] info           # project, ledger, categories, open clock (for /clock-out)

The project is the nearest folder holding timesheet.json (see timesheet_common.py).
start   records the start time in the state file (one open clock at a time).
stop    closes it, rounds the duration UP to the configured step (default half hour), and appends a
        row to the 逐日日志 table of the ledger with 来源 = "打卡 HH:MM-HH:MM".
        --start lets you close a clock you forgot to open.
note    deposits what one session finished INTO the open clock without stopping it (several sessions run
        in parallel while one person's clock runs; a session finishing is not the person clocking out).
        Deposits land in a sibling append-only <state>_log.jsonl; stop merges them into the single row
        it writes (dominant --cat by deposit count) and clears them. Only the session holding the
        ledger (or the user) runs stop.
break   logs minutes spent on something unrelated (another project's meeting, lunch) while the clock
        is open; stop subtracts them (plus --deduct) BEFORE rounding and writes 来源 = "打卡 HH:MM-HH:MM 扣除 N h（原因）".
The clock covers everything you do for the project (reading, meetings, chat),
not only assistant sessions; that is the point of running it by hand.
"""
import argparse
import datetime as dt
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timesheet_common as tc  # noqa: E402

tc.utf8_stdio()


def now():
    return dt.datetime.now().replace(second=0, microsecond=0)


def parse_at(s, base=None):
    """'HH:MM' -> today at that time (or on base's date)."""
    base = base or now()
    h, m = s.split(":")
    return base.replace(hour=int(h), minute=int(m), second=0, microsecond=0)


def fmt_min(m):
    """90 -> '1.5 h', 20 -> '20 min'."""
    return f"{m / 60:g} h" if m % 30 == 0 else f"{m} min"


def load_state(cfg):
    if os.path.exists(cfg["state"]):
        with open(cfg["state"], encoding="utf-8") as fh:
            return json.load(fh)
    return None


def save_state(cfg, obj):
    if obj is None:
        if os.path.exists(cfg["state"]):
            os.remove(cfg["state"])
        return
    os.makedirs(os.path.dirname(cfg["state"]), exist_ok=True)
    with open(cfg["state"], "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def append_row(cfg, row):
    """Insert row after the last data row of the 逐日日志 table."""
    with open(cfg["ledger"], encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    head = None
    for i, ln in enumerate(lines):
        if ln.strip() == tc.TABLE_HEAD and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            if any("## 记录" in x for x in lines[:i]):  # the first such table after "## 记录" is the daily log
                head = i
                break
    if head is None:
        sys.exit(f"daily-log table not found in {tc.rel(cfg, cfg['ledger'])}")
    j = head + 2
    while j < len(lines) and tc.ROW_RX.match(lines[j]):
        j += 1
    lines.insert(j, row)
    with open(cfg["ledger"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def log_path(cfg):
    """Sibling of the state file: notes/.clock.json -> notes/.clock_log.jsonl."""
    base = cfg["state"]
    return (base[:-5] if base.endswith(".json") else base) + "_log.jsonl"


def load_deposits(cfg, clock_start=None):
    """Deposits of the open punch (append-only file, one JSON object per line)."""
    p = log_path(cfg)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if clock_start and e.get("clock_start") != clock_start:
                continue
            out.append(e)
    return out


def drop_deposits(cfg, clock_start):
    """Consume one punch's deposits, keep any others. The only place that rewrites the log."""
    p = log_path(cfg)
    if not os.path.exists(p):
        return 0
    keep, gone = [], 0
    with open(p, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
            except ValueError:
                keep.append(ln)
                continue
            if e.get("clock_start") == clock_start:
                gone += 1
            else:
                keep.append(ln)
    if keep:
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(keep) + "\n")
    else:
        os.remove(p)
    return gone


def merge_deposits(deposits):
    """-> (note, result, dominant cat, {cat: count}); one punch is one row, so everything joins."""
    notes, results, cats = [], [], {}
    for e in deposits:
        t = (e.get("note") or "").strip()
        if t:
            who = (e.get("session") or "").strip()
            notes.append("%s（%s）" % (t, who) if who else t)
        for r in (e.get("result") or "").split(","):
            r = r.strip()
            if r and r not in results:
                results.append(r)
        c = (e.get("cat") or "").strip()
        if c:
            cats[c] = cats.get(c, 0) + 1
    cat = max(cats, key=lambda k: cats[k]) if cats else ""
    return "；".join(notes), ", ".join(results), cat, cats


def cmd_note(cfg, args):
    st = load_state(cfg)
    if not st:
        print("[clock] 没有进行中的打卡，投递无处可挂。先 start，或把这段写进口信交给工时 session。")
        return 1
    if not (args.note or args.result):
        print("[clock] --note 或 --result 至少给一个。")
        return 1
    if args.cat and cfg["categories"] and args.cat not in cfg["categories"]:
        print(f"[clock] 提醒：分类「{args.cat}」不在本项目词表里（{' / '.join(cfg['categories'])}），照记不改。")
    entry = {"at": now().isoformat(), "clock_start": st["start"], "session": args.session or "",
             "cat": args.cat or "", "note": args.note or "", "result": args.result or ""}
    with open(log_path(cfg), "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    n = len(load_deposits(cfg, st["start"]))
    start = dt.datetime.fromisoformat(st["start"])
    print(f"[clock] 已投递本段（自 {start:%m-%d %H:%M} 起）第 {n} 条"
          + (f" · {args.cat}" if args.cat else "") + "；钟未停，收工由工时 session 结账。")
    return 0


def cmd_start(cfg, args):
    st = load_state(cfg)
    if st:
        print(f"[clock] 已有打卡未结束：{st['start'][:16].replace('T', ' ')}（{st.get('note') or '无备注'}）。先 stop 或 cancel。")
        return 1
    t = parse_at(args.at) if args.at else now()
    save_state(cfg, {"start": t.isoformat(), "note": args.note or "", "project": cfg["project"]})
    print(f"[clock] 开始 {t:%Y-%m-%d %H:%M} · {cfg['project']}" + (f" · {args.note}" if args.note else ""))
    return 0


def cmd_stop(cfg, args):
    st = load_state(cfg)
    end = parse_at(args.at) if args.at else now()
    if args.start:
        start = parse_at(args.start, end)
        note0 = ""
    elif st:
        start = dt.datetime.fromisoformat(st["start"])
        note0 = st.get("note") or ""
    else:
        print("[clock] 没有进行中的打卡。忘了 start 的话用 --start HH:MM 补。")
        return 1
    if end <= start:
        print(f"[clock] 结束 {end:%H:%M} 不晚于开始 {start:%H:%M}，未记录。")
        return 1
    breaks = list(st.get("breaks") or []) if (st and not args.start) else []
    deduct = sum(int(b.get("minutes") or 0) for b in breaks) + int(args.deduct or 0)
    step = float(cfg["round_hours"])
    span = (end - start).total_seconds() / 3600
    raw = span - deduct / 60
    if raw <= 0:
        print(f"[clock] 扣除 {deduct} min 后不剩工时（时段 {span:.2f} h），未记录。")
        return 1
    hours = max(step, math.ceil(raw / step - 1e-9) * step)
    src = f"打卡 {start:%H:%M}-{end:%H:%M}"
    if deduct:
        why = "、".join(b.get("note") for b in breaks if b.get("note")) or "中途无关事务"
        src += f" 扣除 {fmt_min(deduct)}（{why}）"
    deposits = load_deposits(cfg, st["start"]) if (st and not args.start) else []
    d_note, d_result, d_cat, d_cats = merge_deposits(deposits)
    note = args.note or d_note or note0
    cat = args.cat or d_cat
    if cat and cfg["categories"] and cat not in cfg["categories"]:
        print(f"[clock] 提醒：分类「{cat}」不在本项目词表里（{' / '.join(cfg['categories'])}），照写不改。")
    status = "完成" if (note and cat) else "待填"
    row = f"| {start:%Y-%m-%d} | {cat} | {note} | {args.result or d_result} | {cfg['person']} | {hours:.1f} | {src} | {status} |"
    append_row(cfg, row)
    save_state(cfg, None)
    if deposits:
        drop_deposits(cfg, st["start"])
    ded = f" − 扣除 {fmt_min(deduct)} = {raw:.2f} h" if deduct else ""
    print(f"[clock] 结束 {end:%Y-%m-%d %H:%M} · 时段 {span:.2f} h{ded} → 计 {hours:g} h（进一法）")
    print(f"[clock] 已写入台账 {tc.rel(cfg, cfg['ledger'])}：{row}")
    if deposits:
        who = "、".join(sorted({(e.get("session") or "?") for e in deposits}))
        print(f"[clock] 已并入本段 {len(deposits)} 条 session 投递（{who}）并清空投递文件。")
        if len(d_cats) > 1:
            share = "、".join(f"{k}×{v}" for k, v in sorted(d_cats.items(), key=lambda kv: -kv[1]))
            print(f"[clock] 投递跨 {len(d_cats)} 个分类（{share}），已按条数最多的「{d_cat}」归类；"
                  "台账脚注补一句「N 个 session 并行，时段只计一次」。")
    if status == "待填":
        print("[clock] 分类/任务未填，状态=待填；用 /clock-out 让 Claude 补齐，或手改台账。")
    return 0


def cmd_break(cfg, args):
    st = load_state(cfg)
    if not st:
        print("[clock] 没有进行中的打卡，无处记录中断；收工时用 stop --deduct MIN 扣。")
        return 1
    if args.minutes <= 0:
        print("[clock] --minutes 要是正整数。")
        return 1
    st.setdefault("breaks", []).append({"minutes": int(args.minutes), "note": args.note or "", "at": now().isoformat()})
    save_state(cfg, st)
    total = sum(int(b.get("minutes") or 0) for b in st["breaks"])
    print(f"[clock] 已记中断 {args.minutes} min" + (f" · {args.note}" if args.note else "")
          + f"；本段累计扣除 {fmt_min(total)}，收工 stop 时先扣再取整。")
    return 0


def cmd_status(cfg, args):
    st = load_state(cfg)
    if not st:
        return 0
    start = dt.datetime.fromisoformat(st["start"])
    el = (now() - start).total_seconds() / 3600
    breaks = st.get("breaks") or []
    ded = sum(int(b.get("minutes") or 0) for b in breaks)
    extra = ""
    if ded:
        extra = f"（中途无关事务 {fmt_min(ded)} 已记，收工自动扣除：{'、'.join(b.get('note') or '无备注' for b in breaks)}）"
    dep = load_deposits(cfg, st["start"])
    if dep:
        who = "、".join(sorted({(e.get("session") or "?") for e in dep}))
        extra += f"（已收 {len(dep)} 条 session 投递：{who}，收工时并进同一行）"
    print(f"[clock] 打卡进行中：自 {start:%m-%d %H:%M} 起，已 {el:.1f} h" + (f" · {st['note']}" if st.get("note") else "") + extra + "。结束时 /clock-out。")
    return 0


def cmd_cancel(cfg, args):
    st = load_state(cfg)
    if not st:
        print("[clock] 没有进行中的打卡。")
        return 0
    gone = drop_deposits(cfg, st["start"])
    save_state(cfg, None)
    print(f"[clock] 已取消 {st['start'][:16].replace('T', ' ')} 的打卡，不记录。"
          + (f"同时丢弃本段 {gone} 条 session 投递。" if gone else ""))
    return 0


def cmd_info(cfg, args):
    print(f"[timesheet] 项目 {cfg['project']} · 根目录 {cfg['root']}")
    ext = f" · 对外表 {tc.rel(cfg, cfg['external_ledger'])}（任务行前缀「{cfg['external_prefix']}」）" if cfg["external_prefix"] else ""
    print(f"[timesheet] 台账 {tc.rel(cfg, cfg['ledger'])}{ext}")
    print(f"[timesheet] 分类词表：{' / '.join(cfg['categories']) or '（未配置）'}")
    dirs = tc.transcript_dirs(cfg)
    print(f"[timesheet] transcript 目录：{', '.join(os.path.basename(d) for d in dirs) or '（未找到）'}")
    if load_state(cfg):
        return cmd_status(cfg, args)
    print("[clock] 没有进行中的打卡。")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    tc.add_project_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start"); p.add_argument("--note", default=""); p.add_argument("--at", help="HH:MM, backdate the start")
    p = sub.add_parser("stop"); p.add_argument("--note", default=""); p.add_argument("--cat", default=""); p.add_argument("--result", default="")
    p.add_argument("--at", help="HH:MM, end time if not now"); p.add_argument("--start", help="HH:MM, when no clock was started")
    p.add_argument("--deduct", type=int, default=0, help="minutes to subtract before rounding (interruptions not logged with break)")
    p = sub.add_parser("break"); p.add_argument("--minutes", type=int, required=True, help="minutes spent on something unrelated")
    p.add_argument("--note", default="", help="why (e.g. 其他项目会议)")
    p = sub.add_parser("note", help="a finished session deposits its work into the open clock; does not stop it")
    p.add_argument("--note", default=""); p.add_argument("--cat", default=""); p.add_argument("--result", default="")
    p.add_argument("--session", default="", help="first 8 chars of the depositing session id")
    sub.add_parser("status"); sub.add_parser("cancel"); sub.add_parser("info")
    args = ap.parse_args()
    cfg = tc.load(args.project)
    return {"start": cmd_start, "stop": cmd_stop, "break": cmd_break, "note": cmd_note,
            "status": cmd_status, "cancel": cmd_cancel, "info": cmd_info}[args.cmd](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
