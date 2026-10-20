#!/usr/bin/env bash
# link_academic_skills.sh -- macOS/Linux counterpart of link_academic_skills.ps1.
#
# Links the central academic skill set into one paper repo:
#   .claude/skills/<skill>      -> symlink to ~/Documents/claude-design/skills/academic/<skill>
#   .claude/academic-rules.md   <- copy of ~/Documents/claude-design/rules/academic-rules.md
#   CLAUDE.local.md             gets the import line "@./.claude/academic-rules.md"
#   .git/info/exclude           gets a managed block so none of the above is ever committed
#
# Usage (run at the repo root, or pass the repo path):
#   link_academic_skills.sh link   [repo]
#   link_academic_skills.sh unlink [repo]
#   link_academic_skills.sh doctor [repo]
# Restart the Claude Code session afterwards: skills and imports are read at session start.
#
# Same semantics as the .ps1 (verified there 2026-09-09): "@" imports resolve only real relative
# paths inside the repo, so the rules are copied in rather than imported from the central location.
set -euo pipefail

ACTION="${1:-link}"
REPO="$(cd "${2:-.}" && pwd)"
CENTRAL="${CENTRAL:-$HOME/Documents/claude-design/skills/academic}"
RULES="${RULES:-$HOME/Documents/claude-design/rules/academic-rules.md}"
IMPORT_LINE="@./.claude/academic-rules.md"
LOCAL_HEADER="# Personal, machine-local Claude settings for this repo (not committed; see .git/info/exclude)."
BLOCK_START="# >>> academic-skills (managed by link_academic_skills.ps1)"
BLOCK_END="# <<< academic-skills"
RULES_REL=".claude/academic-rules.md"
REGISTRY="$(cd "$(dirname "$0")" && pwd)/linked-repos.txt"

skills_dir="$REPO/.claude/skills"
local_md="$REPO/CLAUDE.local.md"
rules_dst="$REPO/$RULES_REL"
tag="$(basename "$REPO")"

git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || { echo "Not a git repo: $REPO" >&2; exit 1; }
exclude_path="$(git -C "$REPO" rev-parse --git-path info/exclude)"
case "$exclude_path" in /*) ;; *) exclude_path="$REPO/$exclude_path" ;; esac

central_skills() {
  [ -d "$CENTRAL" ] || { echo "Central dir not found: $CENTRAL" >&2; exit 1; }
  for d in "$CENTRAL"/*/; do
    n="$(basename "$d")"
    case "$n" in _*) continue ;; esac
    [ -f "$d/SKILL.md" ] && echo "$n"
  done
}

is_link_into_central() {  # $1 = path
  [ -L "$1" ] || return 1
  local t; t="$(readlink "$1")"
  case "$t" in "$CENTRAL"/*) return 0 ;; *) return 1 ;; esac
}

write_exclude_block() {  # entries on stdin (may be empty)
  local entries; entries="$(cat)"
  mkdir -p "$(dirname "$exclude_path")"
  local kept=""
  if [ -f "$exclude_path" ]; then
    kept="$(awk -v s="$BLOCK_START" -v e="$BLOCK_END" '$0==s{skip=1;next} $0==e{skip=0;next} !skip' "$exclude_path")"
  fi
  {
    [ -n "$kept" ] && printf '%s\n' "$kept"
    if [ -n "$entries" ]; then
      printf '%s\n' "$BLOCK_START"
      printf '%s\n' "$entries"
      printf '%s\n' "$BLOCK_END"
    fi
  } > "$exclude_path.tmp"
  mv "$exclude_path.tmp" "$exclude_path"
}

set_import_line() {
  if [ ! -f "$local_md" ]; then
    printf '%s\n%s\n' "$LOCAL_HEADER" "$IMPORT_LINE" > "$local_md"
    return
  fi
  grep -vxF -- "@~/Documents/claude-design/rules/academic-rules.md" "$local_md" > "$local_md.tmp" || true
  grep -qxF -- "$IMPORT_LINE" "$local_md.tmp" || printf '%s\n' "$IMPORT_LINE" >> "$local_md.tmp"
  mv "$local_md.tmp" "$local_md"
}

registry_add() { touch "$REGISTRY"; grep -qxF -- "$REPO" "$REGISTRY" || printf '%s\n' "$REPO" >> "$REGISTRY"; }
registry_remove() { [ -f "$REGISTRY" ] && { grep -vxF -- "$REPO" "$REGISTRY" > "$REGISTRY.tmp" || true; mv "$REGISTRY.tmp" "$REGISTRY"; }; }

do_link() {
  [ -f "$RULES" ] || { echo "Central rules file not found: $RULES" >&2; exit 1; }
  mkdir -p "$skills_dir"
  local linked=() skipped=()
  while IFS= read -r s; do
    dst="$skills_dir/$s"
    if [ -e "$dst" ] || [ -L "$dst" ]; then
      if is_link_into_central "$dst"; then linked+=("$s"); continue; fi
      skipped+=("$s"); echo "skip $s: $dst exists and is not a link into the central dir" >&2; continue
    fi
    ln -s "$CENTRAL/$s" "$dst"
    linked+=("$s")
  done < <(central_skills)

  cp -f "$RULES" "$rules_dst"
  set_import_line
  {
    printf '%s\n' "CLAUDE.local.md" "$RULES_REL"
    for s in "${linked[@]}"; do printf '.claude/skills/%s\n' "$s"; done  # no trailing slash: symlinks are files to git
  } | write_exclude_block
  registry_add
  echo "[$tag] linked ${#linked[@]} skill(s); rules copied to $RULES_REL"
  [ ${#skipped[@]} -gt 0 ] && echo "  skipped (real folders): ${skipped[*]}"
  return 0
}

do_unlink() {
  local removed=0
  if [ -d "$skills_dir" ]; then
    for p in "$skills_dir"/*; do
      if is_link_into_central "$p"; then rm "$p"; removed=$((removed+1)); fi
    done
  fi
  rm -f "$rules_dst"
  printf '' | write_exclude_block
  if [ -f "$local_md" ]; then
    grep -vxF -e "$IMPORT_LINE" -e "@~/Documents/claude-design/rules/academic-rules.md" "$local_md" > "$local_md.tmp" || true
    if grep -vxF -- "$LOCAL_HEADER" "$local_md.tmp" | grep -q '[^[:space:]]'; then mv "$local_md.tmp" "$local_md"; else rm -f "$local_md.tmp" "$local_md"; fi
  fi
  registry_remove
  echo "[$tag] removed $removed link(s); rules copy, exclude block and import line cleared"
}

do_doctor() {
  local problems=0
  while IFS= read -r s; do
    dst="$skills_dir/$s"
    if [ ! -L "$dst" ] && [ ! -e "$dst" ]; then echo "  unlinked: $s"; problems=$((problems+1))
    elif [ -L "$dst" ] && [ ! -e "$dst" ]; then echo "  dangling: $s -> $(readlink "$dst")"; problems=$((problems+1))
    elif ! is_link_into_central "$dst"; then echo "  real folder (not a link): $s"; fi
  done < <(central_skills)
  if [ -f "$rules_dst" ]; then
    if ! cmp -s "$RULES" "$rules_dst"; then echo "  stale rules copy: $RULES_REL differs from central"; problems=$((problems+1)); fi
  else echo "  rules copy missing: $RULES_REL"; problems=$((problems+1)); fi
  if [ -f "$local_md" ] && grep -qxF -- "$IMPORT_LINE" "$local_md"; then :; else echo "  import line missing in CLAUDE.local.md"; problems=$((problems+1)); fi
  if [ -f "$exclude_path" ] && grep -qxF -- "$BLOCK_START" "$exclude_path"; then :; else echo "  exclude block missing in .git/info/exclude"; problems=$((problems+1)); fi
  echo "[$tag] doctor: $problems problem(s)"
}

case "$ACTION" in
  link)   do_link ;;
  unlink) do_unlink ;;
  doctor) do_doctor ;;
  *) echo "usage: $0 link|unlink|doctor [repo]" >&2; exit 2 ;;
esac
