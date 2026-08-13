# Vault Template — 个人知识库骨架（Claude Code + Obsidian）

这是一套"外部记忆系统"的可复用骨架：用 Obsidian 做知识库，用 Claude Code
做记录员和管理员。**你说话（中文口语），Claude 分类、写入、维护（英文笔记）**，
任何项目里的 Claude 都能通过 `/vault` 查库、`/log-to-vault` 记录成果。

> 给 Claude 的说明：如果你是在帮用户初始化这套系统，先通读本 README 和
> `vault/CLAUDE.md`，理解三层结构后再动手。设计背景详见同仓库的
> `onboarding-guide-zh.md`（第 9.1 节"外部记忆系统"）。

## 三层结构

| 层 | 内容 | 装到哪 |
|---|---|---|
| **知识库本体** | `vault/` — 文件夹骨架 + CLAUDE.md 操作手册 + 路由/写作规则 + 笔记模板 | 复制为你自己的库，如 `C:\Users\<你>\Documents\The Vault\` |
| **全局命令** | `global-commands/` — `/vault`（查库）、`/log-to-vault`（记录） | `~/.claude/commands/`，需替换路径占位符 |
| **进阶工具** | `advanced/` — vault-health 巡检、session 索引 | 库用起来之后再装，见 `advanced/README.md` |

## 安装步骤

### 1. 建库

1. 把 `vault/` 整个文件夹复制到你想放库的位置，改名（如 `The Vault`）
2. 在库目录里 `git init`（推荐，历史即备份）
3. 用 Obsidian "Open folder as vault" 打开它
4. 打开 `CLAUDE.md`，把 `_(fill in)_` 的部分留着 — Claude 用起来会自动维护

### 2. 装全局命令

1. 把 `global-commands/vault.md` 和 `log-to-vault.md` 复制到 `~/.claude/commands/`
   （即 `C:\Users\<你>\.claude\commands\`，没有就新建）
2. 在两个文件里做替换（文件开头的注释里有说明）：
   - `{{VAULT_PATH}}` → 你的库的绝对路径，如 `C:\Users\<你>\Documents\The Vault`
   - `{{DOCUMENTS_PATH}}` → 项目的上级目录，如 `c:/Users/<你>/Documents/`
3. 替换完删掉文件开头的 SETUP 注释

### 3. 全局个人配置（可选但推荐）

在 `~/.claude/CLAUDE.md` 写几行你的个人偏好，例如：

```markdown
# User Config

## Language
对话用中文，代码/文档/commit 用英文。

## Cross-project Memory
Use `/vault` to query my personal vault (projects, people, decisions) from any project.
```

### 4. 开始用

- 在库目录开 Claude Code，直接说话："今天做了 X"、"认识了一个人叫 Y" —
  Claude 会按 `.claude/rules/routing-rules.md` 自动分类写入并汇报
- 在**任何**项目里：`/vault 某项目进展如何` 查库；干完活 `/log-to-vault` 记录
- `Templates/` 里是四种笔记模板（日记/人物/研究项目/实践项目），Claude 建新
  笔记时会参考

## 核心设计逻辑（为什么这样搭）

1. **CLAUDE.md 是索引不是仓库** — 它只放结构、规则、项目一句话状态；
   细节都在各自的笔记里。Claude 每次会话自动读它，所以它越精炼越好
2. **路由规则显式化** — "什么信息进哪个文件夹"写死在
   `.claude/rules/routing-rules.md`，Claude 不用猜
3. **角色边界** — 库里的 Claude 只记录和整理，不做项目本身的活；
   项目工作在项目自己的目录里做（各有各的 Claude 上下文）
4. **Sessions/ 是给 Claude 的检索层，不是给人读的** — `/log-to-vault`
   写的 digest 靠 `[[wikilink]]` 反链把信息送到项目/人物页面上
5. **Recent Activity 滚动窗口** — CLAUDE.md 里只保留最近约 6 周的动态，
   更早的原样归档到 `Sessions/Activity-Archive.md`，防止索引膨胀

## 目录清单

```
vault-template/
├── README.md                      ← 本文件
├── vault/                         ← 库骨架（复制这个）
│   ├── CLAUDE.md                  ← 操作手册（结构/规则/状态索引）
│   ├── .claude/rules/             ← routing-rules + writing-rules
│   ├── Templates/                 ← 4 个笔记模板
│   ├── Profile/About.md           ← 个人信息桩文件
│   └── Daily|Projects|Plans|Ideas|Tools|People|Sessions/   ← 空骨架
├── global-commands/               ← /vault + /log-to-vault（占位符待替换）
└── advanced/                      ← vault-health + session 索引（后装）
```
