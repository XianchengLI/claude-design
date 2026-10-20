"""Measured context size of a Claude Code session, read from its transcript usage fields.

  python ctx_usage.py <session id prefix>

Prints aggregates only (token counts + a by-source character breakdown), never content.
Why: self-estimates run low. In capp-career-agent (2026-09-17) the tower estimated 110k / 125k / 165k
while the transcript said ~100k more each time; it hit 278k before anyone noticed.
"""
import collections
import glob
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
if len(sys.argv) < 2:
    sys.exit(__doc__)
hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{glob.escape(sys.argv[1])}*.jsonl"))
if not hits:
    sys.exit(f"no transcript matches {sys.argv[1]!r}")
p = max(hits, key=os.path.getmtime)
rows = [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]

usage, ids = [], {}
by = collections.Counter()
for r in rows:
    m = r.get("message") or {}
    if r.get("type") == "assistant":
        u = m.get("usage") or {}
        if u:
            total = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            usage.append((r.get("timestamp", "")[11:16], total, u.get("output_tokens", 0)))
        for c in m.get("content") or []:
            if c.get("type") == "tool_use":
                inp = c.get("input") or {}
                key = c["name"] + (":" + os.path.basename(inp.get("file_path", "")) if c["name"] == "Read" else "")
                ids[c["id"]] = key
                by["(tool_use args)"] += len(json.dumps(inp, ensure_ascii=False))
            elif c.get("type") == "text":
                by["(assistant text)"] += len(c.get("text", ""))
            elif c.get("type") == "thinking":
                by["(thinking)"] += len(c.get("thinking", ""))
    elif r.get("type") == "user":
        cs = m.get("content")
        if isinstance(cs, str):
            by["(cross-session messages)" if "cross-session-message" in cs else "(user/system text)"] += len(cs)
            continue
        for c in cs or []:
            if c.get("type") == "tool_result":
                t = c.get("content")
                n = len(t) if isinstance(t, str) else sum(len(x.get("text", "")) for x in t or [] if isinstance(x, dict))
                by[ids.get(c.get("tool_use_id"), "?")] += n
            elif c.get("type") == "text":
                by["(cross-session messages)" if "cross-session-message" in c["text"] else "(user/system text)"] += len(c["text"])

if not usage:
    sys.exit("transcript has no usage fields yet")
print("transcript:", os.path.basename(p))
print("first request context tokens:", usage[0][1], "@", usage[0][0], "(timestamps are UTC)")
print("LATEST request context tokens:", usage[-1][1], "@", usage[-1][0])
step = max(1, len(usage) // 10)
print("trajectory (k):", [(t, n // 1000) for t, n, _ in usage[::step]])
print("assistant output tokens total:", sum(o for _, _, o in usage))
print("--- characters (not tokens) by source, top 14 ---")
for k, v in by.most_common(14):
    print(f"{v:>9}  {k}")
