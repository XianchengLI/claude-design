---
name: literature-review
description: Conduct systematic literature reviews using academic databases (PubMed, Google Scholar, Semantic Scholar). Search, screen, synthesize findings thematically, and verify citations. For research papers, thesis chapters, or standalone reviews.
---

# Literature Review

Conduct systematic literature reviews with rigorous methodology. Search multiple databases, synthesize findings thematically, and verify all citations.

## When to Use This Skill

- Conducting a systematic or scoping literature review
- Writing the literature review section of a paper
- Synthesizing knowledge on a specific topic
- Identifying research gaps and future directions

## Core Workflow

### Phase 1: Planning

1. Define research question (use PICO for clinical topics)
2. Set inclusion/exclusion criteria (date range, language, study types)
3. Identify 2-3 databases to search

### Phase 2: Search

**Databases and access methods**:

| Database | Access | Best for |
|----------|--------|----------|
| Google Scholar | WebSearch | Broad coverage, citation counts |
| PubMed | WebFetch E-utilities API | Biomedical, MeSH terms |
| Semantic Scholar | WebFetch API | Cross-disciplinary, 200M+ papers |
| OpenAlex | WebFetch API | Open access, bibliometrics |

**PubMed search tips**:
- MeSH terms: `"Diabetes Mellitus"[MeSH]`
- Field tags: `[Title]`, `[Title/Abstract]`, `[Author]`
- Boolean operators: AND, OR, NOT
- Date filters: `2020:2024[Publication Date]`

**Document all searches**: query string, database, date, result count.

### Phase 3: Screening

Title screening -> Abstract screening -> Full-text review.

**Source-pointer rule**: every load-bearing quote or claim taken from a screened paper gets a
source pointer (page / section / figure) recorded at extraction time — quotes without pointers
cannot be re-verified later (working-paper vs published-version drift is real: load-bearing
quotes have been found absent from the published text). A paper's own narration of field history
or prior work is context, never independently verified evidence — verify against the primary
source before citing it as fact.
Document exclusions at each stage. Create PRISMA flow if systematic.

### Phase 4: Synthesis

**Organize thematically, NOT study-by-study**:
- Group by themes (3-5 major themes)
- Compare and contrast across studies within each theme
- Identify consensus, controversies, and gaps

### Phase 5: Citation Verification

Use the citation-management skill to verify all DOIs and claim-citation alignment.
Verification is leveled: **full-text first**; abstract-level only when full text is unavailable (declare it + log an upgrade TODO). Output a `reference_ledger.md` (template: `assets/reference-ledger.md` bundled with the citation-management skill) recording each reference as `unverified` / `abstract` / `full-text` — hard metric: 0 unverified before the review is finalized.

## Citation Styles Quick Reference

| Style | In-text | Common in |
|-------|---------|-----------|
| Vancouver | Superscript numbers [1,2] | Biomedical |
| APA | (Author, Year) | Social sciences |
| Nature | Superscript numbers | Natural sciences |

## Best Practices

- Search minimum 2-3 databases for comprehensive coverage
- Include recent literature (last 5-10 years for active fields)
- Synthesize thematically, not as a list of paper summaries
- Assess study quality (Cochrane ROB for RCTs, Newcastle-Ottawa for observational)
- Verify all citations with CrossRef API before finalizing

## Common Pitfalls

1. Single database search — misses relevant papers
2. Study-by-study summary instead of thematic synthesis
3. No quality assessment — treats all evidence equally
4. Unverified citations — always check DOIs resolve
5. Too broad or too narrow search terms
