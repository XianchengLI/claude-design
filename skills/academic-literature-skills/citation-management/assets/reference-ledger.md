---
name: Reference Verification Ledger
tags: [references, verification, manuscript-tracking]
---

# Reference Verification Ledger — <Manuscript Title>

One row per cited reference. This file is the **hard metric** for citation verification: it must exist in every project that runs any citation flow (adding, editing, or auditing citations), and it travels with the manuscript.

Copy to the manuscript project root as `reference_ledger.md`.

## Verification Levels

| Level | Meaning | Requirement |
|-------|---------|-------------|
| `unverified` | Cited but content never checked | **Blocks submission.** Metadata resolution alone (DOI exists) does NOT lift this. |
| `abstract` | Claim checked against abstract/metadata only | Allowed ONLY when full text is genuinely unavailable (paywall, no PMC, no Zotero PDF). Must record the reason + a TODO to upgrade. |
| `abstract (snippet)` | Not even the abstract was retrievable; evidence = search-engine-indexed snippets, consistent across ≥2 independent searches | Weakest acceptable tier. Counts as `abstract` in the hard metric, but the `snippet` annotation is mandatory so it is never mistaken for a real abstract read. Same reason + TODO requirement. |
| `full-text` | Claim checked against the paper's full text | The default target. Sources: PMC, publisher HTML/PDF, Zotero attachment (`zotero_get_item_fulltext` / `zotero_read_pdf_pages`). |

**Rules (hard):**
1. Full-text verification is the default; abstract level is a declared fallback, never a silent shortcut.
2. Every `abstract` row MUST have a reason in the last column and a matching entry in the TODO section.
3. `unverified` count must be 0 before submission (gate 1b cannot PASS otherwise).
4. Support verdict is per claim-attachment, not per paper: if one paper backs multiple claims, check each attachment (add rows or list claims in one row).
5. **Verdict inheritance:** a verdict carried over from an earlier audit round keeps its ORIGINAL evidence level and date; it never silently becomes "verified" in a later round. Each row records when and at what level it was last actually checked. A "weak but acceptable" at abstract level stays exactly that until someone re-checks at full text (which may confirm, or overturn it).

## Summary (hard metric — update every audit pass)

- **Total refs:** N | **full-text:** N | **abstract:** N | **unverified:** N
- **Last audit:** YYYY-MM-DD | **Manuscript version:** <label/commit>

## Ledger

| Citekey | Title (short) | DOI/PMID | Used for (section: claim) | Level | Support verdict | Checked | Why not full-text / notes |
|---------|---------------|----------|---------------------------|-------|-----------------|---------|---------------------------|
| e.g. `li2024pilot` | PD pilot study | 10.xxxx/yyyy | Intro: PD forums understudied | full-text | strong | 2026-07-29 | — |
|  |  |  |  |  |  |  |  |

`Support verdict` values: `strong` / `partial` / `background` / `contradicts` / `hijacked` (real paper, wrong claim) / `attribution-creep` (the manuscript's OWN interpretation, gloss, or inference presented as the cited work's finding — e.g. "show that" for a viewpoint paper, a mechanism neither source states, an inference sandwiched between two real citations). `contradicts`, `hijacked`, or `attribution-creep` → fix the citation or the claim before submission. Attribution creep is the dominant full-text-level failure mode and is systematically invisible at abstract level — it is a primary reason full-text is the default.

## TODO — upgrade abstract-level to full-text

- [ ] `<citekey>` — why blocked (e.g. paywalled, no PMC) — where to get full text (library access / ILL / author request)

## Withdrawn / replaced

Track refs removed during audit so they don't silently come back.

| Citekey | Why removed | Date | Replacement (if any) |
|---------|-------------|------|----------------------|
|  |  |  |  |
