"""Project-wide context scan over Claude Code transcripts: where single sessions spend their context.

  python ctx_scan.py <project dir slug> [--since YYYY-MM-DD] [--detail <id prefix> ...]

  slug = the folder name under ~/.claude/projects/, e.g. c--Users-Xianc-Documents-capp-career-agent

Prints aggregates only, never content:
  - peak context per session (top 30), request count, cumulative context tokens (sum over requests);
  - worker sessions (no shift-in / tower-in): how many cross 200k / 300k / 400k, median context at the
    first edit of a .py source file (= orientation cost), how many dispatch any subagent;
  - --detail: composition of that session's context up to its peak, by source, plus the files read or
    written in it and the largest single tool results.
Why: 2026-10-23 scan of capp-career-agent found 132/184 workers over the 200k line and a median 164k
before the first source edit; ctx_usage.py looks at one session, this looks at the distribution.
Limits: composition is in characters, not tokens; thinking text is not in the transcript.
"""
import collections
import datetime
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
slug = args.pop(0)
since, detail = "0000-00-00", []
while args:
    a = args.pop(0)
    if a == "--since": since = args.pop(0)
    elif a == "--detail": detail, args = args, []
D = os.path.expanduser(f"~/.claude/projects/{slug}/")
TOWER = re.compile(r"shift-in|tower-in")


def tokens(u):
    return u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)


def size(c):
    t = c.get("content")
    return len(t) if isinstance(t, str) else sum(len(x.get("text", "")) for x in t or [] if isinstance(x, dict))


def scan(p):
    rows = [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]
    s = dict(id=os.path.basename(p)[:8], peak=0, n=0, cum=0, model="", start="", tower=False,
             first_edit=None, agents=0, at200=None, snap=None)
    ids, by, files, big = {}, collections.Counter(), collections.defaultdict(lambda: [0, 0]), []
    ctx = 0
    for r in rows:
        if not s["start"] and r.get("timestamp"): s["start"] = r["timestamp"][:16]
        m = r.get("message") or {}
        if r.get("type") == "assistant":
            s["model"] = m.get("model", s["model"])
            u = m.get("usage") or {}
            if u:
                ctx = tokens(u); s["n"] += 1; s["cum"] += ctx
                if s["at200"] is None and ctx > 200_000: s["at200"] = s["n"]
                if ctx > s["peak"]:
                    s["peak"] = ctx; s["snap"] = (by.copy(), {k: v[:] for k, v in files.items()}, big[:])
            for c in m.get("content") or []:
                t = c.get("type")
                if t == "tool_use":
                    inp, name = c.get("input") or {}, c["name"]
                    by["[args] " + name] += len(json.dumps(inp, ensure_ascii=False))
                    if name in ("Agent", "Task"): s["agents"] += 1
                    fp = inp.get("file_path", "")
                    if name in ("Edit", "Write") and s["first_edit"] is None and fp.endswith(".py") and "scratchpad" not in fp:
                        s["first_edit"] = ctx
                    if name == "Write": files["W " + os.path.basename(fp)][0] += 1; files["W " + os.path.basename(fp)][1] += len(inp.get("content", ""))
                    if name == "Read": ids[c["id"]] = "Read", "R " + os.path.basename(fp)
                    elif name == "Bash": ids[c["id"]] = "Bash", (inp.get("command") or "")[:90]
                    else: ids[c["id"]] = name, None
                elif t == "text": by["(assistant text)"] += len(c.get("text", ""))
        elif r.get("type") == "user":
            cs = m.get("content")
            if isinstance(cs, str):
                if TOWER.search(cs[:3000]): s["tower"] = True
                by["(user/system text)"] += len(cs); continue
            for c in cs or []:
                if c.get("type") == "tool_result":
                    n = size(c); kind, key = ids.get(c.get("tool_use_id"), ("?", None))
                    by[kind + " results"] += n
                    if kind == "Read": files[key][0] += 1; files[key][1] += n
                    if n > 8000: big.append((n, key or kind))
                elif c.get("type") == "text":
                    if TOWER.search(c["text"][:3000]): s["tower"] = True
                    by["(user/system text)"] += len(c["text"])
    return s


res = [s for s in (scan(p) for p in glob.glob(D + "*.jsonl")
                   if datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d") >= since) if s["n"] >= 20]
if not res:
    sys.exit(f"no sessions with >= 20 requests under {D} since {since}")
res.sort(key=lambda s: -s["peak"])
med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0
print(f"sessions since {since}: {len(res)}; cumulative context tokens {sum(s['cum'] for s in res) / 1e6:.0f}M, "
      f"{sum(s['cum'] for s in res if s['peak'] >= 300_000) / sum(s['cum'] for s in res) * 100:.0f}% from sessions peaking >= 300k")
print(f"{'id':8} {'role':6} {'model':18} {'peak_k':>6} {'reqs':>5} {'cum_M':>6} start")
for s in res[:30]:
    print(f"{s['id']:8} {'tower' if s['tower'] else 'worker':6} {s['model'][:18]:18} {s['peak'] // 1000:>6} {s['n']:>5} {s['cum'] / 1e6:>6.1f} {s['start']}")
w = [s for s in res if not s["tower"]]
fe = [s for s in w if s["first_edit"]]
print(f"\nworkers {len(w)}: peak >200k {sum(s['peak'] > 200_000 for s in w)}, >300k {sum(s['peak'] > 300_000 for s in w)}, "
      f">400k {sum(s['peak'] > 400_000 for s in w)}; used a subagent {sum(s['agents'] > 0 for s in w)}")
print(f"workers with a .py source edit {len(fe)}: median context at first edit {med([s['first_edit'] for s in fe]) // 1000}k, "
      f"median peak {med([s['peak'] for s in fe]) // 1000}k")
for pre in detail:
    s = next((x for x in res if x["id"].startswith(pre)), None)
    if not s: print(f"\n{pre}: not found"); continue
    by, files, big = s["snap"]; tot = sum(by.values()) or 1
    print(f"\n=== {s['id']} peak {s['peak'] // 1000}k, {s['n']} requests, crossed 200k at request {s['at200']}, chars up to peak {tot // 1000}k")
    for k, v in by.most_common(10): print(f"  {v / tot * 100:5.1f}%  {v // 1000:>5}k  {k}")
    print("  files (count / chars):", ", ".join(f"{k}:{c}x/{n // 1000}k" for k, (c, n) in sorted(files.items(), key=lambda x: -x[1][1])[:10]))
    for n, k in sorted(big, reverse=True)[:5]: print(f"  {n // 1000:>4}k  {k}")
