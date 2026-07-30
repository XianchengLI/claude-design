# SKILL.md Design Patterns

> Learned from [PleasePrompto/notebooklm-skill](https://github.com/PleasePrompto/notebooklm-skill) (3,544 stars, 2026-02)

## Template: Complex Skill Structure

A well-designed SKILL.md for non-trivial skills should have these layers:

```
1. frontmatter      - name, description, trigger method
2. When to Use      - specific trigger conditions (beyond description)
3. Critical Rules   - correct/wrong comparison, prevent common errors
4. Core Workflow    - step-by-step with exact commands
5. Decision Flow    - linear decision tree or flowchart
6. Behavior Rules   - what Claude should do AFTER getting results
7. Troubleshooting  - common error -> fix table
8. Limitations      - explicit boundaries
```

## Pattern 1: Trigger Conditions

Don't rely solely on `description` in frontmatter. Explicitly list activation triggers:

```markdown
## When to Use This Skill
Trigger when user:
- Mentions [keyword] explicitly
- Shares [URL pattern]
- Asks to [verb] their [noun]
- Uses phrases like "...", "...", "..."
```

**Why**: Claude's skill selection is based on description matching. Expanded triggers
with example phrases improve hit rate for implicit requests.

## Pattern 2: Correct/Wrong Comparison

For tools with multiple calling conventions, use visual contrast:

```markdown
## Critical: Always Use [correct method]

# correct:
python scripts/run.py auth_manager.py status

# wrong:
python scripts/auth_manager.py status  # Fails without venv!
```

**Why**: Claude tends to take shortcuts. Explicit wrong examples act as guardrails.
Especially useful when the wrong path *looks* reasonable.

## Pattern 3: Decision Flow

Give Claude a complete decision tree, not scattered steps:

```markdown
## Decision Flow
Check auth status
    -> If not authenticated -> Setup auth
    -> Check/Add notebook -> Activate notebook
    -> Ask question -> Evaluate answer
    -> Need more info? -> Ask follow-up (loop)
    -> Synthesize all answers -> Respond to user
```

**Why**: Complex skills have conditional branching. Without a flow, Claude may
skip steps (e.g., forgetting auth check) or get stuck in loops.

## Pattern 4: Post-Result Behavior Rules

Tell Claude what to do AFTER receiving tool output, not just how to call tools:

```markdown
## Follow-Up Mechanism (CRITICAL)
1. STOP - Do not immediately respond to user
2. ANALYZE - Compare answer to user's original request
3. IDENTIFY GAPS - Determine if more information needed
4. ASK FOLLOW-UP - If gaps exist, query again with context
5. REPEAT - Continue until information is complete
6. SYNTHESIZE - Combine all answers before responding to user
```

**Why**: This is advanced prompt engineering. Claude's default is "get result, return it."
Behavior rules override this default to produce higher-quality responses.

## Pattern 5: Troubleshooting Table

Pre-empt common failures:

```markdown
## Troubleshooting
| Problem              | Solution                              |
|----------------------|---------------------------------------|
| ModuleNotFoundError  | Use run.py wrapper, not direct call   |
| Authentication fails | Browser must be visible for setup     |
| Rate limit (50/day)  | Wait or switch account                |
| Browser crashes      | Run cleanup with --preserve-library   |
```

**Why**: Without this, Claude enters retry loops or asks the user for help on
solvable problems. The table gives it a lookup path.

## Pattern 6: Explicit Limitations

State what the skill CANNOT do:

```markdown
## Limitations
- No session persistence (each question = new browser)
- Rate limits on free accounts (50 queries/day)
- Manual upload required (user must add docs first)
```

**Why**: Prevents Claude from promising functionality that doesn't exist.
Users get frustrated when Claude claims it can do something, then fails.

---

## When NOT to Over-Engineer

Simple skills (like `/save` - 49 lines) don't need all 8 layers.
Use the full template when:

- Skill involves **external tool calls** (APIs, browsers, scripts)
- There are **conditional branches** (auth check, multiple modes)
- **Error states** are likely (network, permissions, rate limits)
- Claude needs to **interpret results** before responding

For simple edit/read tasks, `Task + Process + Style` is sufficient.

---

## Source Article

Also studied: [Chatbots in science: What can ChatGPT do for you?](https://www.nature.com/articles/d41586-024-02630-z)
by Milton Pividori (Nature, Aug 2024). Three lessons for AI in research:

1. **Prompt engineering is critical** - explicit role assignment, clear examples
2. **Distinguish suitable vs unsuitable tasks** - creative work stays human
3. **Writing > Reading with AI** - revision is safer than analysis; human writes first, AI polishes

These principles apply to skill design: a good SKILL.md is essentially
a well-engineered prompt with explicit roles, boundaries, and workflows.
