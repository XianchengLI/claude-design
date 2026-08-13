# Writing Rules

## File Creation
- Use templates from `Templates/` as starting points for new files
- Always include YAML frontmatter with at least `tags`
- All file content in English; Claude communicates with user in Chinese

## Cross-referencing
- Use `[[wikilinks]]` only between notes of the **same category** (e.g., project↔project)
- For cross-category references (project→person, project→CV), use **frontmatter properties** instead:
  - `people: [Name1, Name2]` in project frontmatter to reference people
  - Plain text paths for references to Profile files (e.g., "see Profile/CV.md")
- This keeps the Obsidian graph clean — nodes only connect meaningfully
- Use callouts for important information (`> [!tip]`, `> [!warning]`)
- Use tags for categorization and graph coloring

### Exception: Sessions/ is a retrieval layer
`Sessions/YYYY-MM.md` files (written by `/log-to-vault`) are exempt from the
same-category rule. They **must** use `[[wikilinks]]` inline to cross-category
targets (projects, people, daily notes) so that the Obsidian backlinks panel
surfaces session activity on project/person/daily pages the user actually reads.

Rationale: the digest files themselves are not for human reading — their value
is that their *cross-references* are visible from elsewhere. This is the
opposite of the graph-cleanliness goal the main rule serves, so Sessions get
an explicit carve-out. Filter Sessions/ out of the main graph view if the
extra edges become noisy (Obsidian graph settings → Filters → Files: `-path:Sessions/`).

## Updating Existing Files
- When updating an existing daily note, **append** to the relevant section — never overwrite
- Only record what the user explicitly shares — do not infer or fabricate

## Persistent Fact Capture
When the user mentions a durable fact (file locations, preferences, tools, affiliations, etc.) that is not already recorded, proactively save it to the appropriate location:
- Personal info → `Profile/`
- System/vault config → `CLAUDE.md` or `.claude/rules/`
- People info → `People/`
- Cross-session memory → Claude Code memory

Do not wait for the user to ask — this is automatic. Include captured facts in the brief report.
