# Academic Literature Skills (for Claude Code)

Two self-contained Claude Code skills for literature work in academic writing:

| Skill | What it does |
|-------|--------------|
| `literature-review` | Systematic literature review: research question + inclusion criteria → multi-database search (PubMed / Semantic Scholar / OpenAlex / Google Scholar, all queries logged) → title/abstract/full-text screening with documented exclusions → **thematic** synthesis (not paper-by-paper) → citation verification. |
| `citation-management` | 3-stage citation verification: (1) metadata check against CrossRef/PubMed APIs (search results often return wrong DOIs); (2) claim–citation alignment — does the paper actually support the sentence you wrote? Full-text reading is the default; abstract-only is a declared fallback; (3) whole-manuscript audit recorded in a `reference_ledger.md` with a hard metric: 0 unverified references at submission. |

Bundled assets (inside `citation-management/`):

- `assets/reference-ledger.md` — the ledger template (verification levels, support verdicts incl. "hijacked" and "attribution-creep", TODO tracking). Copy it to your manuscript root as `reference_ledger.md`.
- `scripts/validate_bibtex.py` — batch BibTeX validation (required fields, duplicate keys/DOIs, page-dash format, optional DOI resolution via CrossRef). Pure Python, only optional dependency is `requests` for `--check-dois`.

## Install

Copy both skill folders into either:

- `~/.claude/skills/` — available in all your projects, or
- `<project>/.claude/skills/` — that project only.

Claude Code picks them up automatically; invoke by asking for a literature review / citation check, or explicitly via `/literature-review`, `/citation-management`.

## Updates

**2026-08-19** (bundle refreshed from live skills):

- `validate_bibtex.py --check-dois` now catches **"DOI resolves but points to a different
  paper"** — after CrossRef resolution it compares the returned title (containment match, so a
  registry record lacking the subtitle doesn't false-alarm) and first-author family name against
  the entry. In one real 35-reference audit, 7 of 9 errors were this class.
- New pitfalls documented: Early-Access metadata drift (CrossRef's current volume/pages win),
  missing trailing authors on 5+-author papers (compare author *count*), article-number
  letter/digit confusion (`101880T` ≠ `1018807`).
- New section: **Zotero write-path notes** — the local HTTP API (localhost:23119) is read-only
  (writes return 501); batch fixes go through pyzotero Web mode; the connector endpoint can add
  but never modify.
- `literature-review`: every load-bearing quote/claim from a screened paper now requires a
  **source pointer** (page/section/figure), and a paper's own narration of field history is
  never treated as independently verified.

## Provenance

Based on [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills), substantially extended: leveled verification (full-text default / declared abstract fallback / unverified blocks submission), the reference ledger with hard metrics, verdict inheritance rules, and the bundled validation script. The extensions come from real audits of our own manuscripts — including a case where a genuine, correctly-formatted reference concluded the *opposite* of the sentence citing it, which only full-text reading catches.
