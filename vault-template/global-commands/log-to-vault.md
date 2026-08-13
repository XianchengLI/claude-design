# Log to Vault

<!-- SETUP: replace the two placeholders, then copy this file to
     ~/.claude/commands/log-to-vault.md
     {{VAULT_PATH}}     = absolute path of your vault, e.g. C:\Users\<you>\Documents\The Vault
     {{DOCUMENTS_PATH}} = the parent folder of your projects, e.g. c:/Users/<you>/Documents/  -->

## Your Task

Intelligently extract key information from the current session context and record it to The Vault (`{{VAULT_PATH}}`).

The user may provide a hint after `/log-to-vault` (e.g., `/log-to-vault X功能做完了`), but this is optional. Your job is NOT to blindly copy the hint — instead, analyze the current session and distill what is worth long-term recording.

## What to Capture

Scan the current conversation for information worth persisting. Prioritize:

1. **Decisions made** — technical choices, design decisions, scope changes
2. **Milestones reached** — tasks completed, PRs merged, submissions done
3. **Key findings** — analysis results, bugs discovered, performance numbers
4. **Status changes** — project phase transitions, blockers encountered/resolved
5. **People interactions** — feedback received, meeting outcomes, new collaborators
6. **Plans & next steps** — agreed-upon plans that should be tracked

Skip ephemeral details (debugging steps, intermediate attempts, routine commands).

## Steps

### 1. Analyze Current Context

- Read the conversation history to identify recordable information
- If the user provided a hint, use it to focus — but still check if there's more worth capturing
- Determine the current date by running `date +%Y-%m-%d`

### 2. Read the Vault Index

Read `{{VAULT_PATH}}\CLAUDE.md` to understand the vault structure, active projects, and current state.

### 3. Classify and Route

Route each piece of information following The Vault's routing rules:

| Type | Destination |
|------|-------------|
| Time-bound events (did X today) | `Daily/YYYY-MM-DD.md` — append to relevant section |
| Project progress, decisions, milestones | `Projects/Research/<name>/<name>.md` or `Projects/Practical/<name>/<name>.md` — update Status/Timeline |
| New person, role, affiliation | `People/Full Name.md` |
| Plans, strategies | `Plans/Plan Name.md` |
| CV-worthy achievements | `Profile/CV.md` or `Profile/About.md` |
| Session-level digest (what this whole session was about) | `Sessions/YYYY-MM.md` — append a new block (see Step 5) |

Multiple destinations are normal — a single session often produces both a daily log entry AND a project status update AND a session digest.

### 4. Write to The Vault

- **Daily notes**: Append to existing sections. Never overwrite. Create the file from template if it doesn't exist.
- **Project files**: Update the `## Status` section (phase, last updated date). Add Timeline entries for milestones.
- **All files**: Write content in English. Use YAML frontmatter. Use `[[wikilinks]]` only within same category.

### 5. Write a Session Digest

Append a session-level digest block to `{{VAULT_PATH}}/Sessions/YYYY-MM.md` (current month).

> **Purpose: Claude retrieval, NOT human reading.** The user will not open this
> file. You are writing notes to your future self. Optimize for:
> 1. **Grep hit density** — keywords, project names, people names at the top
> 2. **Information density** — every line should carry a fact or a pointer
> 3. **Non-obvious content only** — skip things retrievable from raw jsonl,
>    `git log`, or the current code. Record what you *could not reconstruct*
>    without this file.
> 4. **Cross-category `[[wikilinks]]` required** — despite the main writing rule
>    forbidding cross-category wikilinks, `Sessions/` is explicitly exempt (see
>    `.claude/rules/writing-rules.md`). Every project, person, and daily note
>    mentioned in the digest MUST be written as `[[Name]]` so the Obsidian
>    backlinks panel surfaces session activity on those pages. This is how the
>    digest's information reaches the user without them reading the digest.

**File handling**:
- If `Sessions/YYYY-MM.md` does not exist, create it with this header:
  ```markdown
  ---
  tags: [sessions, digest]
  ---

  # Session Digests — YYYY-MM

  Structured session-level records written manually via `/log-to-vault`.
  **Purpose: Claude retrieval, not human reading.** Optimized for grep and
  information density.

  ---

  ```
- If it exists, **append** the new block at the end. Never overwrite existing blocks.

**Block format**:

```markdown
## YYYY-MM-DD HH:MM–HH:MM · <project-name> · `<session-short-id-if-known>`
**tags**: #tag1 #tag2 #tag3
**people**: [[Name1]], [[Name2]]  (or — if none)
**projects**: [[ProjectName1]], [[ProjectName2]]  (or (vault-self) if working on vault infra itself)
**daily**: [[YYYY-MM-DD]]  (always the daily note of the session date — creates a backlink on the daily page)
**keywords**: comma, separated, search, terms

### Decisions
- <decision as a single-line assertion; skip the "why" unless non-obvious>
- <another decision>
(If none, omit the section.)

### Facts
- <quantitative or concrete fact that would be hard to reconstruct>
- <numbers, sizes, timings, counts, specific identifiers>
(If none, omit the section.)

### Files touched
- **new** `relative/path/to/file.ext` — one-line purpose
- **mod** `relative/path/to/file.ext` — what changed in one line
(Only files actually created or meaningfully modified. Skip files only read.)

### Gotchas
- <non-obvious problem encountered and how it was resolved or worked around>
- <platform quirk, API caveat, wrong assumption that cost time>
(This is the highest-value section. If you hit any friction at all, record it.)

### References
- <URL, ticket number, external doc, path to related file outside the project>
(If none, omit the section.)
```

**How to fill each field**:
- **Date / time range**: Run `date "+%Y-%m-%d %H:%M"` for the end time. Use the timestamp of the earliest user message you can see for start time (or best estimate if compacted). Round to minutes.
- **Project name in header**: Derive from cwd. Strip `{{DOCUMENTS_PATH}}`. Examples: `The Vault`, `my-app`.
- **Session short id**: If you can determine the current session's id (e.g., from the jsonl filename of the most recently modified file in the matching `~/.claude/projects/<slug>/` folder), include the first 8 hex chars. If not, omit it.
- **tags**: 3–6 hashtag-style topical tags for Obsidian + grep.
- **people**: Wikilinks to real people mentioned or discussed. Use the exact filename from `People/`. Dash if none. Not Claude, not the user.
- **projects**: Wikilinks to the actual project(s) this session worked on. Use the exact project note name from `Projects/Research/` or `Projects/Practical/`. May differ from cwd (e.g., you may be in The Vault editing another project's note). If the work was on vault infrastructure itself, write `(vault-self)` without a wikilink.
- **keywords**: Comma-separated search terms. Include all distinctive nouns, tool names, concept names, file stems — anything a future grep might search for. Plain text, no wikilinks.
- **Decisions**: Single-line assertions of what was chosen. Only record decisions where an alternative was rejected or the choice is non-obvious. Skip routine execution steps.
- **Facts**: Numbers, sizes, counts, identifiers, measurement results — things that would take real work to recover. If the session produced no such facts, omit.
- **Files touched**: Only created/modified files. One line each. Mark `new` or `mod`. Add a brief purpose.
- **Gotchas**: **Most valuable section.** Platform quirks, API caveats, wrong assumptions, hacks around missing tools, unexpected behavior. If you hit *any* friction, record it — even small ones. This is what future-you will thank past-you for.
- **References**: External URLs, ticket/PR numbers, related file paths outside this project, documentation the user pointed at.

**What to leave out** (retrievable elsewhere, wastes tokens):
- Narrative "what was done" sections — the raw jsonl has the full trace
- Reasoning about why each decision was made (beyond one word) — keep assertions, skip essays
- Routine tool calls (read file, grep, etc.) — only the outcome matters
- Restatement of the user's hint

**Skip the digest entirely** if the session was pure Q&A / lookup with no work, no decisions, no new information. Nothing to record.

### 6. Report Back

Respond in Chinese with a brief summary:
- What information was captured
- Which files were created/updated (with paths) — including the session digest if written
- Anything you skipped and why (if relevant)

Keep the report to 3-5 lines max.
