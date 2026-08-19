---
name: citation-management
description: Comprehensive citation management for academic research. Search Google Scholar and PubMed for papers, extract accurate metadata, validate citations, and generate properly formatted BibTeX entries. This skill should be used when you need to find papers, verify citation information, convert DOIs to BibTeX, or ensure reference accuracy in scientific writing.
allowed-tools: [Read, Write, Edit, Bash, WebSearch, WebFetch]
---

# Citation Management

Manage citations for academic manuscripts. Search databases, verify metadata, validate claim-citation alignment, and maintain BibTeX files.

## When to Use This Skill

- Finding papers on Google Scholar or PubMed
- Converting DOIs/PMIDs to BibTeX entries
- Validating existing citations for accuracy
- Verifying that a citation actually supports the claim in the text
- Batch-validating a BibTeX file before submission

## Core Workflow: 3-Stage Verification

### Stage 1: Find & Verify Metadata

Before adding any BibTeX entry:

1. **Search** via WebSearch or CrossRef API
2. **Verify DOI** by querying `https://api.crossref.org/works/{DOI}` with WebFetch
3. **Cross-check** all fields: title, authors, journal, volume, pages, year

**Critical trap**: Search results frequently return wrong DOIs. Always verify independently with CrossRef API.

**Second trap — DOI points to the wrong paper (张冠李戴)**: a DOI that resolves (HTTP 200) can still belong to a *different* paper, e.g. an adjacent article in the same volume. Always compare the CrossRef-returned title and first author against the entry; in one 35-reference audit, 7 of 9 errors were this class. `validate_bibtex.py --check-dois` performs this comparison automatically (containment-based title match, so a CrossRef record lacking the subtitle does not false-alarm).

**Batching**: for >20 references, split into groups of 10–15 across parallel subagents; serial checking is an order of magnitude slower.

**CrossRef API for DOI verification**:
```
GET https://api.crossref.org/works/{DOI}
```
Returns JSON with `message.title`, `message.author`, `message.container-title`, etc.

**PubMed for biomedical papers**:
```
GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmode=json
GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={PMID}&retmode=xml
```

### Stage 2: Verify Claim-Citation Alignment

After placing `\cite{...}`, check the cited paper **actually supports the specific claim**.

**Check paper type first**:

| Paper Type | Can support | Common mistake |
|------------|-------------|----------------|
| Empirical study | Specific findings, statistics | Citing theoretical claims it doesn't make |
| Theoretical paper | Conceptual arguments, models | Using "demonstrated" (use "argued", "proposed") |
| Systematic review | Broad landscape claims | Citing specific mechanisms it only surveys |
| Concept analysis | Definitions, scope | Attributing empirical findings it doesn't report |

**Red flags**:
- Verb mismatch: "demonstrated" for a theoretical paper
- Over-attribution: paper studies X but doesn't claim Y
- Concept drift: paper defines concept A, cited for related concept B

**Verification (leveled — full-text first)**:
- **`full-text` (default)**: read the relevant sections of the paper (PMC, publisher HTML/PDF, Zotero attachment) and confirm the claim.
- **`abstract` (declared fallback only)**: allowed ONLY when full text is genuinely unavailable (paywall, no PMC, no PDF). State this explicitly in your report and log a TODO to upgrade to full-text. Never fall back silently.
- **`unverified`**: content never checked — blocks submission; DOI resolution alone does not count as verification.

If the paper doesn't support the claim: rephrase the claim, or find a better citation.

### Stage 3: Post-Placement Audit → Reference Ledger

After all citations placed:
1. List every `\cite{...}` and the statement it supports
2. Rate each as: confirmed, imprecise, or wrong
3. Fix all wrong immediately; fix imprecise if time permits
4. Record every reference in the project's `reference_ledger.md` (template: `assets/reference-ledger.md` bundled with this skill — copy it to the manuscript root): verification level (`unverified` / `abstract` / `full-text`), support verdict, date, and for `abstract` rows the reason + upgrade TODO. Update the summary counts.

**Hard metric**: `reference_ledger.md` must exist for any manuscript whose citations were touched; 0 `unverified` refs at submission; every `abstract` ref carries a declared reason + TODO.

The bundled template also defines two stricter refinements: `abstract (snippet)` as the weakest acceptable evidence tier, and verdict inheritance (a verdict carried over from an earlier audit keeps its original evidence level and date — it never silently upgrades).

## BibTeX Format Reference

**Standard entry types and required fields**:

```bibtex
@article{key, author, title, journal, year, volume, number, pages, doi, note}
@inproceedings{key, author, title, booktitle, year, pages, doi, note}
@book{key, author, title, publisher, year}
@misc{key, author, title, year, howpublished}
```

**Formatting rules**:
- Page ranges use `--` (not single dash): `pages = {123--145}`
- Protect capitalization with braces: `title = {The {CRISPR} approach}`
- Citation keys: `FirstAuthorYear + keyword` (e.g., `ke2015defining`)
- `doi` field: plain DOI without URL prefix (e.g., `10.1038/nature12345`)

**vancouver.bst workaround**: This BST style ignores the `doi` field. To display DOIs:
```bibtex
note = {doi: \url{https://doi.org/10.xxxx/yyyy}}
```

## Validation Script

Use `scripts/validate_bibtex.py` (bundled with this skill) for batch validation:

```bash
# Basic validation (fields, duplicates, formatting)
python scripts/validate_bibtex.py article.bib

# With DOI resolution via CrossRef API
python scripts/validate_bibtex.py article.bib --check-dois

# JSON output for programmatic use
python scripts/validate_bibtex.py article.bib --json
```

Run it from the skill folder or copy it into the project; it takes the `.bib` path as its only positional argument.

Checks: required fields, duplicate keys/DOIs, similar titles, year format, page dashes, DOI format, note-doi consistency, and (with `--check-dois`) DOI-record mismatch against CrossRef title/first author.

## Zotero Write-Path Notes (tested 2026)

When fixes need to be written back to a Zotero library:

- Zotero 7's local HTTP API (`localhost:23119`) is **read-only** — write operations return 501; flaky zotero-mcp writes usually trace to this layer. Probe with `curl --max-time` to distinguish from Zotero being busy.
- **Batch writes: use pyzotero in Web mode** (userID + API key; full CRUD with built-in 429 backoff).
- Without an API key, the local `/connector/saveItems` endpoint can only ADD items, never modify existing ones.
- Editing `zotero.sqlite` directly is a last resort: Zotero must be closed, and multi-table relations plus version numbers need manual upkeep.
- Before fixing an item, confirm it is actually in the library — an empty title search means the `.bib` came from another source and Zotero needs no correction.

## Common Pitfalls

1. **Search agents hallucinate DOIs** — always verify with CrossRef API before committing
2. **"Classic" citations may not say what everyone thinks** — concept analyses are not empirical evidence
3. **Theoretical papers are not empirical evidence** — adjust verbs: "argued", "proposed", not "demonstrated", "showed"
4. **Same author + different papers** — verify you have the right paper, not just the right author
5. **Preprint vs published version** — use published version DOI when available
6. **Early Access metadata drift** — IEEE-style Early Access papers get new volume/issue/pages/year at formal publication; when the entry and CrossRef disagree, CrossRef's current value wins
7. **Missing trailing authors** — entries for 5+ author papers often record only the first 3–4; compare author *count* against the publisher record
8. **Article-number letter confusion** — article numbers containing letters get misread as look-alike digits (T/7, l/1, O/0), e.g. SPIE `101880T` ≠ `1018807`
