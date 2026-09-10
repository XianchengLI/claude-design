# timesheet · 跨项目打卡与工时台账工具

一份脚本，多个项目。每个项目只放一个 `timesheet.json`，台账仍在各项目自己的 `notes/` 里。
配套的用户级 skill：`~/.claude/skills/clock-in`、`clock-out`、`timesheet`（对所有项目可见，没有配置的项目会直接停）。

| 脚本 | 做什么 |
|---|---|
| `timesheet_clock.py` | `start` / `stop` / `status` / `cancel` / `info`。stop 进一法取整后往台账「逐日日志」表追加一行 |
| `timesheet_audit.py` | 从 Claude Code transcript 出工作块：`--status`（有无未归档天）、`--draft`（写草稿段）、`--rows`、`--window "日期 HH:MM-HH:MM"`（一段打卡内所有 session 做了什么 + 改了哪些文件，给 /clock-out 用） |
| `timesheet_report.py` | 台账出图（内部页 / 对外页 / 三张 PNG），校验内外两表合计一致；`--csv` / `--csv-only` 重生成对外 CSV |
| `timesheet_common.py` | 找项目、读配置。三个脚本都从这里取路径和常量 |

## 项目怎么接入

1. 复制 `timesheet.example.json` 到项目根目录，改名 `timesheet.json`，按项目填：台账路径、分类词表、对外表前缀、里程碑、标题、关键词。
2. 台账 `notes/工时记录.md` 沿用三层结构：`## 任务表（内部，PP 表结构）` → `## 记录（逐日日志）`（表头必须是
   `| 日期 | 分类 | 任务 | 交付 / 成果 | 参与人 | 工时(h) | 来源 | 状态 |`）→ 可选草稿段（`<!-- draft:start -->` … `<!-- draft:end -->`）→ `## 汇总`。
   clock 的 stop 只认「## 记录」之后的第一张这种表。
3. 项目 `.claude/settings.local.json` 的 SessionStart 加一条，开 session 时提示未结束的打卡：
   ```json
   {"type": "command", "command": "python \"C:\\Users\\Xianc\\Documents\\claude-design\\scripts\\timesheet\\timesheet_clock.py\" --project \"<项目根目录>\" status", "timeout": 15}
   ```
4. 可选：项目 `scripts/` 里放三个同名 shim（各 8 行，见 capp-career-agent 或 texwinca-dyeing 的 `scripts/timesheet_*.py`），旧命令 `python scripts/timesheet_clock.py …` 照常可用。

## 怎么找项目

`--project DIR` > 环境变量 `TIMESHEET_PROJECT` > 从当前目录向上找 `timesheet.json`。都没有：打印「本项目不记工时」，退出码 3。

## 配置键

| 键 | 用途 | 默认 |
|---|---|---|
| `project` | 显示名 | 根目录名 |
| `ledger` / `state` | 台账 / 打卡状态文件（相对根目录） | `notes/工时记录.md` / `notes/.clock.json` |
| `external_ledger` / `external_prefix` / `external_csv` | 对外任务表、其任务行第一格的前缀（空 = 不出对外页）、对外 CSV（空 = 不生成） | 见示例 |
| `person` | 打卡行与草稿行的参与人 | `显铖` |
| `categories` | 台账分类词表，`/clock-out` 只能写这些；stop 时写了词表外的分类会提醒 | 空 |
| `report_categories` / `fold` / `fallback_category` | 图表分组（≤ 8 个，顺序固定）、台账分类到图表分组的折叠、未知分类落到哪一组 | = categories / 空 / 最后一组 |
| `exclude_categories` | 不计入合计与图表的分类 | `["其他项目"]` |
| `milestones` / `claim_round` / `report_title` / `report_title_external` / `report_out` | 累计图节点、建议申报小时、两页标题、输出目录 | 见示例 |
| `keywords` | 正则；`--extra` 目录里只保留提到它的工作块 | 空 |
| `transcript_dirs` | `~/.claude/projects/` 下的目录名；默认按项目路径推导（大小写、空格两种拼法都试） | 推导 |
| `round_hours` / `gap_minutes` / `pad_minutes` | 进一法步长、断块间隔、每块启动余量 | 0.5 / 30 / 5 |
| `skip_dirs` | `--window` 列文件时额外忽略的目录名（`.git` `data` `.venv` 等已内置） | 空 |
| `uplift` | C 档估算的上下浮动 | `[0.25, 0.35]` |

## 来历

2026-08 在 texwinca-dyeing 里写成，08-31 复制进 capp-career-agent 后两边各自演化（capp 加了「一段打卡 = 一行」和 `--window`），
09-06 合并为一份并参数化，两个项目改成配置 + shim。
