# Writing Rules

## File Creation
- Use templates from `Templates/` as starting points for new files
- Always include YAML frontmatter with at least `tags`
- All file content in English; Claude communicates with user in Chinese

## Cross-referencing

> [!warning] Precedence over generic Obsidian skills
> If you install a generic Obsidian syntax skill (e.g. kepano's `obsidian-markdown`), it
> teaches "always use wikilinks for in-vault notes". In THIS vault the rules below override
> that advice: wikilinks are same-category only. The skill governs syntax (how to write a
> link); this file governs topology (when to link at all).

- Use `[[wikilinks]]` only between notes of the **same category** (e.g., project↔project)
- For cross-category references (project→person, project→CV), use **frontmatter properties** instead:
  - `people: [Name1, Name2]` in project frontmatter to reference people
  - Plain text paths for references to Profile files (e.g., "see Profile/CV.md")
- This keeps the Obsidian graph clean — nodes only connect meaningfully
- Use callouts for important information (`> [!tip]`, `> [!warning]`)
- Use tags for categorization and graph coloring

### Exceptions to the same-category rule
1. **MOC notes** (tag `moc`, the L0 index layer — see Layer Model below): an
   index's job is pointing at what it indexes, whatever the category.
2. **Sessions retrieval layer**: `Sessions/YYYY-MM.md` digests (written by
   `/log-to-vault`) are **NOT MOCs** (they are L2 chronicles) but keep their
   own carve-out: they **must** wikilink inline to cross-category targets
   (projects, people, daily notes) so the backlinks panel surfaces session
   activity on pages you actually read — the digests themselves are not for
   human reading; their value is their cross-references. Filter
   `-path:Sessions/` in the main graph view if the edge noise bothers.

## Layer Model

Three layers; the layer marker is a **tag** (graph color groups only match tags):

- **L0 index/MOC** — tag `moc`, rendered in a prominent color in every graph
  view. Typical members: `CLAUDE.md` (root MOC), `Skills/Skill-Index` +
  category hubs + `Candidate-Skills` (if you use the skill-map add-on), a
  tools index, a sessions index. A note tagged `moc` must link to something
  (vault-health check 6 enforces this) — an index of vault-external items
  with no notes to link is a reference page, not a MOC. Create a hub only
  where notes have no organic links of their own (e.g. Skills); categories
  that are already networked (Projects, People) get NO artificial hub — it
  would blind the orphan check.
- **L1 content network** — Projects/People/Ideas/Plans/Tools/Profile:
  organic wikilinks per the same-category rule; colored by type tags.
- **L2 chronicles** — Daily notes AND Sessions digests: time-ordered records,
  written once, retrieved by date or backlink.
  **HARD RULE: a chronicle (anything in `Daily/` or `Sessions/`) is NEVER
  tagged `moc`, no matter how many links it accumulates** — layer is defined
  by a note's FUNCTION (diary/log), not by its degree; a digest linking 70
  notes is still a log, not an index (enforced as an error by vault-health
  check 6). Chronicles are records, not knowledge — exclude them from the
  main knowledge graph by default (`-path:Daily/ -path:Sessions/` in the
  graph filter); durable outcomes must already live in the project note
  before a log entry rotates out. Their retrieval surface — backlinks panels
  and date access — is untouched by graph exclusion. Keep a separate
  Timeline view (`path:Sessions/ OR path:Daily/`) where chronicles are the
  subject.

  Salience gradient rule: the higher the layer, the more visible — L0
  prominent, L1 saturated type colors, L2 faintest (dim gray).

## Renames & Moves
Rename or move notes **inside Obsidian** (it rewrites all wikilinks). A rename
or move done outside Obsidian (shell, scripts, Explorer) MUST be followed by a
manual link sweep (`grep` the old name) or a vault-health run — otherwise
every inbound wikilink silently breaks.

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
