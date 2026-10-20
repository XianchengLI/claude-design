#!/usr/bin/env bash
# mac_bootstrap.sh -- set up the Claude layer on a new Mac from the PC's git repos.
#
# Plan: The Vault / Plans/Mac-Migration.md (section 3).
#
# Before running (by hand, once):
#   1. Install Homebrew            https://brew.sh
#   2. brew install gh git
#   3. gh auth login               (GitHub, HTTPS, browser)
#   4. gh repo clone XianchengLI/claude-design ~/Documents/claude-design
#   5. AirDrop the folder `mac-migration-secrets` from the PC Desktop to ~/
#   6. bash ~/Documents/claude-design/scripts/migration/mac_bootstrap.sh
#
# Idempotent: safe to re-run. Nothing here needs sudo.
set -euo pipefail

GH_USER=XianchengLI
MACUSER=$(whoami)
DOCS="$HOME/Documents"
SECRETS="${1:-$HOME/mac-migration-secrets}"
MAC_SLUG_PREFIX="-Users-${MACUSER}-Documents-"

step() { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }

step "1. Homebrew packages"
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew list git >/dev/null 2>&1 || brew install git
brew list gh >/dev/null 2>&1 || brew install gh
brew list node >/dev/null 2>&1 || brew install node
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
brew list --cask powershell >/dev/null 2>&1 || brew install --cask powershell
brew list --cask visual-studio-code >/dev/null 2>&1 || brew install --cask visual-studio-code
brew list --cask obsidian >/dev/null 2>&1 || brew install --cask obsidian

step "2. npm globals (claude, lark-cli, bun, ccusage)"
npm install -g @anthropic-ai/claude-code bun ccusage
# lark-cli: binary + the 28 lark-* skills into ~/.claude/skills (symlinks to ~/.agents/skills)
npx @larksuite/cli@latest install

step "3. GitHub auth + git identity"
gh auth status >/dev/null 2>&1 || gh auth login
gh auth setup-git
git config --global user.name  "XianchengLI"
git config --global user.email "xiancheng.li@hotmail.com"
git config --global --add safe.directory "$HOME/.claude"

step "4. ~/.claude from claude-config"
if [ -d "$HOME/.claude/.git" ]; then
  git -C "$HOME/.claude" pull --ff-only
else
  if [ -e "$HOME/.claude" ]; then
    # a fresh `claude` run or the lark install may already have created it: keep its files
    mv "$HOME/.claude" "$HOME/.claude.pre-migration"
  fi
  gh repo clone "$GH_USER/claude-config" "$HOME/.claude"
  if [ -d "$HOME/.claude.pre-migration" ]; then
    rsync -a --ignore-existing "$HOME/.claude.pre-migration/" "$HOME/.claude/"
    rm -rf "$HOME/.claude.pre-migration"
  fi
fi

step "5. Memory slugs: Windows prefix -> Mac prefix"
shopt -s nullglob
for d in "$HOME/.claude/projects/"[cC]--Users-Xianc-Documents-*; do
  base=$(basename "$d")
  rest=${base#*--Users-Xianc-Documents-}
  new="$HOME/.claude/projects/${MAC_SLUG_PREFIX}${rest}"
  if [ -e "$new" ]; then
    rsync -a "$d/" "$new/" && rm -rf "$d"
    echo "  merged  $base -> $(basename "$new")"
  else
    mv "$d" "$new"
    echo "  renamed $base -> $(basename "$new")"
  fi
done
shopt -u nullglob

step "6. settings.json: Windows paths -> Mac"
python3 - "$HOME" <<'PY'
import json, re, shutil, sys
home = sys.argv[1]
p = f"{home}/.claude/settings.json"
shutil.copy(p, p + ".win-backup")
s = json.load(open(p, encoding="utf-8"))

# C:\Users\Xianc  C:/Users/Xianc  c:/...  /c/Users/Xianc  //c/Users/Xianc  -> $HOME
WIN_HOME = re.compile(r"(?i)(?:/{1,2}c/|c:[/\\]+)Users[/\\]+Xianc")
def fix(x: str) -> str:
    x = WIN_HOME.sub(home, x)
    x = x.replace("\\", "/")
    x = x.replace('"/c/Program Files/nodejs/node"', "node")
    return x

perm = s.setdefault("permissions", {})
perm["allow"] = [fix(a) for a in perm.get("allow", []) if not a.startswith("PowerShell(")]
perm["additionalDirectories"] = [f"{home}/.claude", f"{home}/Documents/The Vault"]

for event, groups in s.get("hooks", {}).items():
    for g in groups:
        for h in g.get("hooks", []):
            if "command" in h:
                h["command"] = fix(h["command"])
if "statusLine" in s and "command" in s["statusLine"]:
    s["statusLine"]["command"] = fix(s["statusLine"]["command"])

json.dump(s, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("  settings.json rewritten (backup: settings.json.win-backup)")
print(f"  allow entries kept: {len(perm['allow'])}; additionalDirectories reset to .claude + The Vault")
PY

step "7. academic-search MCP server venv"
python3 -m venv "$HOME/.claude/mcp_servers/.venv"
"$HOME/.claude/mcp_servers/.venv/bin/pip" install --quiet mcp requests toml lxml

step "8. Secrets from $SECRETS"
if [ -d "$SECRETS" ]; then
  mkdir -p "$HOME/.ssh" "$HOME/.claude/scripts" "$HOME/.claude/channels/discord"
  if [ -f "$SECRETS/mcp.json" ]; then
    python3 - "$SECRETS/mcp.json" "$HOME" <<'PY'
import json, sys
src, home = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
for name, srv in d.get("mcpServers", {}).items():
    srv["command"] = f"{home}/.claude/mcp_servers/.venv/bin/python"
    srv["args"] = [a.replace("\\", "/").replace("C:/Users/Xianc", home) for a in srv.get("args", [])]
json.dump(d, open(f"{home}/.claude/.mcp.json", "w", encoding="utf-8"), indent=2)
print("  .mcp.json written with the Mac python + paths")
PY
  fi
  [ -f "$SECRETS/lit-mcp.ps1" ] && cp "$SECRETS/lit-mcp.ps1" "$HOME/.claude/scripts/lit-mcp.ps1" \
    && echo "  lit-mcp.ps1 copied (still Windows-specific inside: claude.cmd, C:\\Python313 -- edit before use)"
  [ -f "$SECRETS/discord.env" ] && cp "$SECRETS/discord.env" "$HOME/.claude/channels/discord/.env" && echo "  discord .env placed"
  if [ -d "$SECRETS/ssh" ]; then
    cp "$SECRETS/ssh/"* "$HOME/.ssh/"
    chmod 700 "$HOME/.ssh"; chmod 600 "$HOME/.ssh/"*
    echo "  ssh key + config placed"
  fi
  echo "  -> delete $SECRETS once everything works"
else
  echo "  no $SECRETS folder: skipped (AirDrop it from the PC Desktop, then re-run)"
fi

step "9. The Vault + claude-design"
[ -d "$DOCS/The Vault/.git" ]     || gh repo clone "$GH_USER/the-vault"     "$DOCS/The Vault"
[ -d "$DOCS/claude-design/.git" ] || gh repo clone "$GH_USER/claude-design" "$DOCS/claude-design"

step "10. By hand, in this order"
cat <<EOF
  a) claude                       -> log in once (creates ~/.claude/.credentials.json)
  b) in a claude session: /plugin -> install code-simplifier@claude-plugins-official and claude-hud@claude-hud
                                     (everything-claude-code, discord were installed on the PC but disabled)
  c) lark-cli auth login (brand feishu); re-request the scopes granted 2026-10-18
                                     -> "$DOCS/The Vault/Tools/Lark-CLI.md"
  d) VS Code: Claude Code extension, Settings Sync on
  e) Obsidian: Open folder as vault -> "$DOCS/The Vault"
  f) Verify in one session opened in "$DOCS/The Vault":
       MEMORY.md index loads · [Last Session] + vault-sync lines print · /vault answers · lark-cli posts as the bot
EOF
