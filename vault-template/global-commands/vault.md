# Vault Query

<!-- SETUP: replace every {{VAULT_PATH}} below with the absolute path of your
     vault, e.g. C:\Users\<you>\Documents\The Vault  — then copy this file to
     ~/.claude/commands/vault.md -->

## Your Task

Query the user's Obsidian vault ("The Vault") to find information about their projects, CV, people, plans, or past decisions.

## Steps

### 1. Parse the Query

The user's question follows `/vault`. Examples:
- `/vault 某项目的最新进展`
- `/vault 我CV里的工作经历`
- `/vault 某某人是谁`

### 2. Read the Vault Index

First, read `{{VAULT_PATH}}\CLAUDE.md` to understand the vault structure and active projects.

### 3. Search the Vault

Based on the query, search the appropriate location:

| Topic | Where to look |
|-------|--------------|
| Project info | `The Vault/Projects/Research/` or `The Vault/Projects/Practical/` |
| CV, skills, publications | `The Vault/Profile/CV.md` |
| Personal info, background | `The Vault/Profile/About.md` |
| People | `The Vault/People/` |
| Daily logs | `The Vault/Daily/` |
| Plans & strategies | `The Vault/Plans/` |

Use Grep to search across multiple files if the topic isn't immediately clear. The vault root is `{{VAULT_PATH}}\`.

### 4. Respond

- Answer the user's question concisely in Chinese
- Cite which vault file(s) the information came from
- If the information isn't in the vault, say so clearly
