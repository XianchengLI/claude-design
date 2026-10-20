---
name: tower-out
description: 控制塔交班（tower kit 通用版）——检查本班还有什么只在对话里没落盘，覆盖写接力棒 handover，给一段简短说明。项目根有 tower.json 且本 session 是控制塔（SESSIONS 表「主题」列写着 control tower）时，用户说 /tower-out、交班、这一班收了时使用。干活 session 收工用 /task-close。
user-invocable: true
allowed-tools: [Bash, Read, Edit, Write, Grep, Skill]
---

# /tower-out — 控制塔交班

上位规则：`.claude/tower-rules.md` 的 Control tower 节。路径全部取自 `tower.json` 的 `files`。
控制塔是常驻岗位，session 轮换着上岗。**本 skill 的核心动作是检查未落盘，接力棒文件只是副产品**：下一班只靠文件接班，不继承任何对话。

## 0. 确认身份

`sessions` 表本行的**主题列**写着 `control tower` 才继续，否则回一句「不是控制塔，收工用 /task-close」。判据是主题列，不是主 ✓（✓ 只是 CLAUDE.md 写权，hook 会把它漂给任意新 session）。

## 1. 逐类检查未落盘（不能跳）

每类给结论：已落 / 需补 / 无；需补的当场补完。

| 检查 | 落点 | 问自己 |
|---|---|---|
| 本班决策 | `decisions` | 有没有改了别人（包括未来的自己）会依赖的东西却没写？ |
| 任务清单 | `tasks` | 进行中是真实状态吗？新冒出的事进 Queue 了吗？本班让哪些排队行的前提失效了？ |
| 各线状态 | `memory` | 哪条线的状态、证据或下一步变了却没改行？ |
| 技术发现 | `gotchas` | 尤其是推翻旧结论的，写了吗？ |
| 规则 | CLAUDE.md + `inbox` | inbox 里有待合并的条目吗？合完只按锚点删已合的条目。**合并前后都看一眼 CLAUDE.md 字数和预算**：超了就先删或改成脚本，不能只加不减 |
| 成本 | 项目的成本记录 | 本班有付费调用吗？用量记了吗？ |

被推翻的结论就地止血：旧处加失效标注并指向新结论，grep 一遍所有引用。

## 2. 覆盖写接力棒 `handover`

按模板的七段写（本班做了什么 / 裁决与理由 / 在跑·在等 / 悬而未决 / 本班让哪些排队行过时 / 下一班第一件事 / 零碎坑）。
只写各正本里没有的东西，不复制状态；复制就等于造出第二份 MEMORY。「裁决与理由」一段从 `tower_log` 本班的 rule / send 行抽取。「悬而未决」一段最重要。
时刻取本机 `date`。

## 3. 给用户的说明（3–5 行）

落了哪几处（文件名即可）、本班自主裁了哪几条（每条一句为什么）、悬而未决剩几条、下一班第一件事。要用户当场答的放进最末的 `## ❓ Open questions (N)` 块。

## 4. 收尾

- 工时：`"timesheet": true` 且有常驻工时 session 时只投递 note，不停钟；否则 /clock-out。
- 提示用户：开新 session 后用 `/tower-in` 接班。SESSIONS 表的行由 hook 处理，不要手改主列。

## 红线

- 未落盘检查不能跳。
- 不把状态复制进接力棒。
- 交班时不开新活。
