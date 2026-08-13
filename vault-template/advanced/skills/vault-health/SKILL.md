---
name: vault-health
description: Run a structural health check on The Vault (broken wikilinks, active-project status drift, orphan People/Ideas notes, frontmatter compliance, Recent Activity rotation). Use when the user asks for a vault 巡检 / health check / 体检, monthly maintenance, or asks whether the vault structure has problems.
---

# Vault Health Check

Read-only structural audit of the vault. No LLM analysis in the script itself —
regex + file metadata only (~1s). Claude's job is to run it, interpret, and fix.

## Run

```
python .claude/scripts/vault_health.py
```

Options: `--stale-days 45` (project drift), `--idea-days 90` (stale seeds),
`--window-days 56` (Recent Activity rotation), `--write` (save report to
`Tools/Vault-Health-Report.md` — only when the user asks for a persisted report).

## Interpreting results

Report findings to the user in Chinese, grouped by section, with a recommended
action per finding. Do NOT auto-fix; propose fixes and wait for confirmation,
EXCEPT trivial mechanical repairs the user already approved in the same session.

Per-section guidance:

1. **Broken wikilinks** — three distinct causes; label each:
   - typo/rename (e.g. `[[PD Pilot]]` vs `PD-Pilot`) → fix the link;
   - missing People note for a real person mentioned in Sessions → offer to
     create `People/<Name>.md` (Sessions links are allowed to dangle briefly —
     they mark notes worth creating, per writing-rules carve-out);
   - missing Daily note referenced by a Session digest → usually fine to leave;
     flag only.
2. **Status drift** — project listed Active in CLAUDE.md but untouched
   (note mtime AND Daily mentions both old). Ask the user: still active,
   or move to Completed/Paused?
3. **Orphans / stale seeds** — Ideas untouched >90d: ask keep/merge/kill.
   People notes with zero references: candidate for deletion or linking.
4. **Frontmatter** — writing-rules require YAML frontmatter with `tags`.
   Safe to fix mechanically after user confirms the list.
5. **Rotation** — if flagged, perform the Recent Activity rotation per the
   rule in CLAUDE.md (move old entries verbatim to `Sessions/Activity-Archive.md`).

## Cadence

Monthly, or after any big reorganization. If the user wants it automated,
suggest adding it to a monthly reminder — do not wire hooks without asking.
