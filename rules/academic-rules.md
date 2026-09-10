# Academic Rules (imported by paper repos)

Loaded only in repos that do manuscript / literature work. `scripts/link_academic_skills.ps1` copies this
file to `<repo>/.claude/academic-rules.md` (git-excluded) and writes the `CLAUDE.local.md` import line
`@./.claude/academic-rules.md`. The copy exists because Claude Code resolves `@` imports only for real
relative paths inside the repo: `@~/...`, `@C:/...` and paths behind a junction are silently ignored
(verified 2026-09-09). Edit THIS file, then run `link_academic_skills.ps1 link -All` to refresh every
linked repo; `doctor` hash-checks each copy against this one.
Moved out of the global `~/.claude/CLAUDE.md` on 2026-09-09 so non-academic projects stop paying for them.

## Academic Project Structure
When setting up a new Overleaf repo or working across analysis/manuscript repos, follow the standard two-repo workflow.
Run `/vault Academic Project Structure` to load the full guide (covers SYNC.md template, figure sync, repo layout).

## Citation Verification (CRITICAL)
Any work touching citations (adding, editing, auditing) requires content verification of every touched reference; DOI resolution alone is not verification. **Full-text first** (PMC / publisher / Zotero PDF); abstract-level ONLY when full text is unavailable, and then it must be explicitly declared and logged as a TODO to upgrade. Every project running a citation flow maintains `reference_ledger.md` at the manuscript root (template: `The Vault/Templates/reference-ledger.md`) with per-reference level: `unverified` / `abstract` / `full-text`. Hard metric: 0 unverified at submission; every abstract row carries reason + TODO.

## Data Availability Statements
When drafting or auditing a Data/Code Availability statement, use the template `The Vault/Templates/data-availability-statement.md` (7 access routes, statement patterns, anti-patterns, HealthUnlocked worked example). Never accept bare "available upon request" wording without a specific restriction reason and access route.

## Methods/Results Separation (academic writing)
Every analysis reported in Results (including sensitivity, supplementary, and exploratory analyses) must be pre-specified in Methods first; Results (and the abstract) report findings only, not the method or rationale (STROBE convention). Never introduce an analysis de novo in Results or an appendix. When you add a method to Methods, correspondingly trim its now-duplicated restatement/rationale from Results (method → Methods, findings → Results). Keep the abstract's Methods consistent with the main Methods (don't mention an analysis in one but not the other).

## Academic skills
The academic skill set (nature-*, literature-review, citation-management, latex-to-word, scientific-writing, lit-mcp) lives in `~/Documents/claude-design/skills/academic/` and is junction-linked into this repo's `.claude/skills/` by the same script. Upgrade them there (skill-adoption workflow), never edit the linked copies as if they were project files.
