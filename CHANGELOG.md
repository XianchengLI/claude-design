# 更新日志 / Changelog

简单版更新记录：每条写"加了什么、解决什么问题、怎么用"。

## 2026-08-19 — 文献技能包上线（academic-literature-skills）

`skills/academic-literature-skills/`：两个可安装技能——`literature-review`（系统化检索 →
筛选 → 主题式综合，关键引文强制带页码级出处指针）+ `citation-management`（三段式引用
核查：元数据 → 论点-引文匹配（默认读全文）→ 全稿台账审计，投稿硬指标 0 条未核查）。
附台账模板和 BibTeX 校验脚本；脚本能抓"DOI 能解析但指向另一篇论文"这类最高发的引用
错误（真实审计中 9 个错误里 7 个是这类）。源自 K-Dense 技能包，用我们自己稿件的真实
审计大幅扩展。文件夹直接拷进 `~/.claude/skills/`，或下载同名 zip。

## 2026-08-19 — vault-template 同步：三层模型 + vault-health 检查 6

把 vault 侧实际用起来之后的两处改进同步进模板：

- **writing-rules 新增"Layer Model"三层模型**：L0 索引层（`moc` 标签，图谱高亮）/
  L1 内容网络（同类 wikilink）/ L2 时序记录（Daily + Sessions，**无论积累多少链接
  永远不算索引**，默认从主知识图谱里过滤掉）。解决的问题：日记和月度摘要链接一多，
  图谱就被它们统治，知识结构反而看不见。另加两条实践规则：改名/移动必须在 Obsidian
  内做（否则入链全断），以及通用 Obsidian 语法技能与本 vault 链接拓扑规则的优先级
  声明。
- **vault-health 新增检查 6（MOC 层完整性）**：`moc` 标签但零出链、hub 级链接量却
  没标 `moc`、Daily/Sessions 误标 `moc`（硬错误），外加"高频空链排名"（同一个
  不存在的目标被 ≥2 处引用 → 大概率是该建而没建的笔记，不是笔误）。点子来自
  arscontexta 与 second-brain-lint 的调研，重新实现为本模板的轻量脚本。

## 2026-08-18 — 技能管理体系：怎么评估、安装、升级、盘点你的 skills

一天里同步了一个 20-skill 的学术技能包、替换掉一个被超越的旧技能、评估了 8 个来路不一的
repo 之后，把踩过的坑沉淀成两件可复用的东西：

- **`skills/skill-adoption/`** — 新技能：第三方 skill 的评估/安装/升级工作流（10 条规则 +
  决策流程图）。核心思想：只看名字会判错，必须读正文；本地有同类的要"取长补短"双向优化而
  不是装两份或直接跳过；声明的依赖要查本体（很多是软依赖）；升级前先 grep 自己的私人定制
  （否则会被静默冲掉，真实事故）；装前必须安全扫描（真的遇到过教 agent 绕过用户授权的
  marketplace skill）。拷进 `~/.claude/skills/` 即用。
- **`vault-template/advanced/skill-map/`** — vault 插件：已装技能的活体清单生成器。扫描全局
  + 所有项目 + 插件的 skill/command，在 Obsidian vault 里生成每技能一页的笔记 + 分类 hub +
  索引页，图谱直接变成技能地图。双层设计：机器层每次重新生成，`%% MANUAL %%` 以下的手工
  笔记永远保留。附两个登记册模板：**Candidate-Skills**（评估过但没装的，记"翻盘条件"，下次
  找新技能先查这里）和 **Skill-Lineage**（被替换/退役的技能世系，再遇到同族候选直接识别，
  不用重新评估）。安装说明见 `vault-template/advanced/README.md` 第 3 节。

## 2026-08-13 — vault-template

个人 vault 系统（Obsidian + Claude Code）的可复用骨架：目录结构、CLAUDE.md 操作手册、
路由/写作规则、`/vault` + `/log-to-vault` 命令、可选的 vault-health 体检插件。内附中文
搭建指南。

## 2026-08-04 — 中文入门指南

`onboarding-guide-zh.md`：写给 Claude Code 新手朋友的完整入门（架构、commands/skills/
MCP/hooks 的区别与选型、工作模式、从 0 到 1 的路径）。

## 2026-02-16/17 — 初始内容

`skill-design-patterns.md`（SKILL.md 结构模板 + 6 个设计模式）、`skill-cleanup-log.md`
（K-Dense 技能包瘦身实录）、`mcp-guide.md`（MCP 架构与选型）。
