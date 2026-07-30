# K-Dense Skill Cleanup Log

> Date: 2026-02-16
> Source: [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills) (8,757 stars)

## Context

Installed 7 project-level skills in `lurking/.claude/skills/`. Six were unmodified K-Dense originals; one (humanizer) was custom. Total: 4,366 lines. Problems:

1. **Commercial spam** — every file ended with K-Dense Web promotion paragraph
2. **Non-existent script references** — `scripts/plot_template.py`, `references/algorithms.md`, etc. (never created)
3. **Cross-skill references** — cited skills not installed (seaborn, gget, bioservices)
4. **Bloat** — generic tutorials better served by Claude's training knowledge
5. **Unsupported frontmatter** — `allowed-tools` not recognized by Claude Code IDE

## Before/After

| Skill | Before (lines) | After (lines) | Reduction |
|-------|----------------|---------------|-----------|
| citation-management | 1,114 | 116 | 90% |
| scientific-writing | 719 | 88 | 88% |
| literature-review | 638 | 83 | 87% |
| statistical-analysis | 631 | 114 | 82% |
| matplotlib | 360 | 92 | 74% |
| networkx | 437 | 118 | 73% |
| **Total (6 skills)** | **3,899** | **611** | **84%** |

humanizer (468 lines) untouched — not from K-Dense, good quality.

## Key Decisions

### Delete script references, not create scripts
Most referenced scripts wrapped functionality Claude can do natively:
- `scripts/plot_template.py` → Claude generates matplotlib code directly
- `references/algorithms.md` → Claude knows NetworkX API from training

**Exception**: Created `scratchpad/validate_bibtex.py` (465 lines) for batch BibTeX validation. This provides independent value because it combines parsing, DOI verification via CrossRef API, and vancouver.bst note-doi consistency checks — multi-step logic worth codifying.

### Replace `allowed-tools` with nothing
`allowed-tools` is not a supported SKILL.md frontmatter attribute. Supported attributes: `name`, `description`, `argument-hint`, `compatibility`, `disable-model-invocation`, `license`, `metadata`, `user-invokable`. Removed from scientific-writing and literature-review.

### Keep skills focused on decisions, not tutorials
**Good skill content**: test selection decision trees, API access patterns, APA reporting templates, colormap selection rules.
**Bad skill content**: basic matplotlib tutorial, NetworkX installation guide, "what is a graph" explanations.

Principle: a skill should help Claude make the *right choice* quickly, not teach it the *basics* it already knows.

## What Was Kept From Each Skill

| Skill | Kept | Removed |
|-------|------|---------|
| citation-management | 3-stage verification workflow, CrossRef API, PubMed E-utilities, vancouver.bst workaround, validate_bibtex.py reference | K-Dense plugin references, Zotero integration, generic BibTeX tutorial |
| scientific-writing | Two-stage writing process, IMRAD structure, writing principles, reporting guidelines table, rejection reasons | Graphical abstract mandate, field-specific terminology (molecular bio, chemistry), Nano Banana Pro references |
| literature-review | 5-phase workflow, database access table, PubMed search tips, citation styles, thematic synthesis rules | gget/bioservices/datacommons skill references, quality assessment rubrics |
| statistical-analysis | Test selection decision tree, assumption checking code, effect size table, APA templates, power analysis | Bayesian analysis section, verbose methodology explanations |
| matplotlib | OO interface rule, publication defaults, plot type table, multi-panel patterns, colormap rules, gotchas | 3D plots, animation, GUI integration, basic tutorial content |
| networkx | Graph type table, DataFrame integration, key metrics code, community detection, visualization with centrality | Graph generators catalog, installation guide, "common workflow pattern" |

## Lessons for Future Skills

1. **~100 lines is the sweet spot** — enough for decisions and patterns, not so much it wastes context
2. **Tables over prose** — decision tables (test selection, colormaps, plot types) are Claude's most useful reference format
3. **Code snippets should be patterns, not tutorials** — show the *recommended* way, not every possible way
4. **Remove what Claude already knows** — it knows matplotlib basics from training; the skill should add project-specific conventions
5. **One real script > ten referenced phantoms** — validate_bibtex.py does more than all the missing K-Dense scripts combined
