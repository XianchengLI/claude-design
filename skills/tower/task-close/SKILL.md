---
name: task-close
description: 干活 session 收工验收（tower kit 通用版）——对着任务清单那一行的完成标准逐条要证据，判定能不能收，把只在对话里的东西路由进各正本，最后给一段 4 行口信。项目根有 tower.json 时，用户说 /task-close、收工、这个 session 完了吗、可以收了吗时使用。控制塔 session（SESSIONS 表「主题」列写着 control tower）收工用 /tower-out；没有 tower.json 的项目用 /wrap。
user-invocable: true
allowed-tools: [Bash, Read, Edit, Write, Grep, Glob, Skill]
---

# /task-close — 干活 session 收工验收

上位规则：项目的 `.claude/tower-rules.md`（由 `tower_init.py` 生成）。所有路径从项目根的 `tower.json` 的 `files` 取，下文用键名指代（`tasks` / `memory` / `sessions` / `decisions` / `gotchas` / `inbox`）。

本 skill 做两件事：把「感觉差不多了」换成「逐条对完成标准要证据」；把要带回去的东西全部落盘，口信只是冗余通知，不是传递通道。

## 0. 定位这一行

1. 读 `tower.json`；在 `sessions` 表找本 session 那行。主题列写着 `control tower` → 停，回一句「控制塔收工走 /tower-out」。
2. 在 `tasks` 的进行中段找 session id 对应的行，它的**完成标准**是唯一的验收锚点。
3. 例外：找不到行（临时指派）→ 锚点 = 用户第一条指令 + 中途追加的要求，收工时补一行直接进 Done，注明「非清单行」；完成标准写得无法判 → 先当场补清楚；做了不止一行 → 每行分别判。

## 1. 机械检查（先跑，不靠回忆）

```bash
git status --short && git log --oneline -5
```
`tower.json` 的 `code_repos` 里每个仓也跑一遍，外加 `git worktree list`。

- 有未提交的改动：说清楚是要提交，还是本来就该留在工作区。
- 本次跑过批或调过付费 API：逐条结果和 token 用量存盘了吗？跑批登记了吗？
- `sessions` 表本行三格（主题 / 分支 / 独占）填齐了吗？
- **重读本 session 写过的每个共享文件，确认自己写的那段还在。** 共享文件是读—改—写，别的 session 整体写回时会静默吞掉你的追加。这一项不能省。

## 2. 完成度对照表（核心，不能跳）

| 完成标准（照抄，不改写、不放宽） | 结论 | 证据（路径 § / commit / run 目录 / 数字） |
|---|---|---|

- 没有证据就是未达成。「跑通了」「应该没问题」都不算证据。
- 收工时不放宽标准。觉得标准不合理，要明说「X 该改成 Y，理由…」，交给控制塔或用户裁。
- 上下文长的 session 自评会偏乐观，拿不准就往未达成判。

结论三档，明确写出来：✅ 达标 → 走第 3 步；⚠️ 部分达标 → 剩余不到 15 分钟就现在做完，否则拆一行进 Queue，本行按实际完成度移走并写「余：…」；❌ 未达标 → 写清卡点，行不移 Done，停下问是继续做还是先收。

## 3. 落盘路由（每类都要给结论：已落 / 需补 / 无）

| 类 | 落点 |
|---|---|
| 决策（含否掉的方案） | `decisions` |
| 一次性坑 / 技术发现 | `gotchas` |
| 评测数字、跑批 | 项目自己的评测正本 + 跑批登记 |
| 新冒出的待办 | `tasks` 的 Queue（五个字段齐全 + `config:`） |
| 想加的规则 | 持主 ✓ 的直接改 CLAUDE.md（**先看预算**：超了就删一条或改成脚本）；其他 session 写进 `inbox` |
| 某条线的状态变了 | `memory` 对应那一行（改行，不追加小节） |

被推翻的旧结论就地加失效标注，并指向新结论，再 grep 一遍有谁引用它。

**交付到外部环境的改动**（合进会自动部署的分支、发给别人跑的脚本）：还要写一段「部署侧依赖」，逐项列出这次改动依赖、要由运行环境提供的东西（环境变量、连接、网络地址、新包），每项写怎么核过对方环境也有；核不了的写清「缺了代码会怎样：报错 / 走退路 / 悄悄给错答案」。出现「核不了 + 悄悄给错答案」的行就不算可交付。

## 4. 收工四步

1. `tasks`：行从进行中移到 Done（`日期 | 任务 + 关键数字 | 落点 | 余：…`），并把 Ready to start 里本行的启动卡整段删掉。删完数一下 ``` 必须成对。
2. `memory` 改对应线那一行。
3. 工时：`tower.json` 里 `"timesheet": true` 时，如果 `sessions` 表里有常驻工时 session 且不是你，**不要 /clock-out**（打卡是项目级单一时钟），改为投递 `python ~/Documents/claude-design/scripts/timesheet/timesheet_clock.py note --session <前8位> --cat <分类> --note "…" --result "落点"`；没有常驻工时 session 才 /clock-out。
4. 口信（≤ 4 行代码块）。有控制塔通讯名（`sessions` 表控制塔那行的 `agent <名字>`）就用 SendMessage 发过去，同时在回复里打印一份；没有就请用户复制：

```
#<行号> 收工：<一句话结果>。
已落：<文件名>。
要控制塔看的：<inbox N 条 / Queue 新增 #N / 无>。
偏差与跨 session 影响：<跳过的步骤 / 动了别人的哪处 / 未提交改动随谁走 / 无>。
```

前三行只是冗余通知，不能有只写在口信里、没落盘的内容；第 4 行是唯一允许只出现在口信里的。最后提示用户可以关掉本 session（SESSIONS 行由 SessionEnd hook 删）。

## 红线

- 收工时不开新活，新冒出的事进 Queue。
- 不改别人独占的文件；共享文件只按锚点追加。
- 判定没达标就不走完流程。本 skill 不是收工许可证。
