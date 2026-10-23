# tower · 多 session 协作起步包

把 capp-career-agent 在 2026-09-05 → 09-17 摸出来的多 session 协作流程，抽成可以装进任意项目的通用版本。
方法论、效果评估和已知失效模式见 Vault `Tools/Multi-Session-Control-Tower.md`。本 README 只讲怎么装、装了什么。

## 先定级，别默认上最重的

| 级 | 什么时候 | 装什么 |
|---|---|---|
| L1 | 单 session，或偶尔两个 | **不装本包**。用户级 `/wrap` + 项目 MEMORY.md 就够 |
| L2 | 经常 2 个 session 并行、持续数周 | tower.json + SESSIONS hook（登记 / 独占拦截 / CLAUDE.md 写权）+ 任务清单 + `/task-close` + 判断包 |
| L3 | 持续 ≥ 3 个并行，需要有人常驻排期 | L2 + 控制塔岗（`/tower-in` `/tower-out`、接力棒、控制塔日志、inbox 合并、上下文实测） |

低于门槛时，治理成本比它省下的多。CAPP 的教训：规则 8 天涨了 3.3 倍，每个 session 开局都要为它付 token。

## 装

```bash
python ~/Documents/claude-design/scripts/tower/tower_init.py init --project <项目根> --level 2 [--code-repo ../代码仓]
python ~/Documents/claude-design/scripts/tower/tower_init.py doctor --project <项目根>   # 或 doctor --all
python ~/Documents/claude-design/scripts/tower/tower_init.py unlink --project <项目根>   # 撤掉链接与 hook，数据文件保留
```

`init` 可以重复跑。改了本包或 tower.json 之后重跑一次，就会重新生成规则副本。具体动作：
1. 缺 `tower.json` 就按 `templates/tower.example.json` 建（已有的不覆盖；改级别直接改文件）；
2. 缺什么正本文件就按模板建（tasks / decisions / gotchas / inbox，L3 另加 handover / tower_log，外加 MEMORY.md）；
3. 规则渲染成 `<项目>/.claude/tower-rules.md`，从 `CLAUDE.local.md` 用 `@./.claude/tower-rules.md` 导入。**项目自己的 CLAUDE.md 不动**；
4. skill 用 junction 挂进 `<项目>/.claude/skills/`，源在 `claude-design/skills/tower/`；
5. 三个 hook 合并进 `<项目>/.claude/settings.local.json`；
6. SESSIONS 表、规则副本、CLAUDE.local.md、skill 链接写进 `.git/info/exclude`（无 BOM）；
7. 项目路径登记到 `linked-projects.txt`。

## 文件

| 文件 | 作用 |
|---|---|
| `tower_init.py` | init / doctor / unlink |
| `sessions_hook.py` | SessionStart 登记并打印 SESSIONS 表、任务摘要、代码仓 worktree 和 CLAUDE.md 预算警告；PreToolUse 拦截写别人独占的文件，以及非 ✓ session 改 CLAUDE.md；SessionEnd 删行。hook 出错一律放行 |
| `ctx_usage.py` | 从 transcript 的 usage 字段读 session 真实上下文，不靠自估 |
| `ctx_scan.py` | 全项目扫一遍：各 session 峰值、干活 session 过 200k / 300k / 400k 的个数、第一次改源码时的上下文（摸代码成本）、单个 session 的上下文构成（`--detail`） |
| `tower_common.py` | 找项目根、读配置（`--project` > `TOWER_PROJECT` > 从当前目录向上找 tower.json） |
| `templates/` | tower.json 示例、规则片段（L2 主体 + L3 附加）、各正本模板 |

skill（`../../skills/tower/`）：`task-close`（干活 session 收工验收）、`judge-bundle` / `judge-bundle-run`（判断包打包与执行）；L3 另有 `tower-in` / `tower-out`（控制塔接班 / 交班）。
这几个 skill 故意不与 CAPP 的项目版（task-out / shift-in / shift-out / judge-pack / judge-run）同名：CAPP 保留原版，照常运行。

## tower.json 键

| 键 | 用途 | 默认 |
|---|---|---|
| `level` | 2 或 3 | 2 |
| `files.*` | 各正本路径（sessions / tasks / handover / inbox / tower_log / memory / claude_md / decisions / gotchas / judge_dir） | 见示例 |
| `task_sections` | 任务清单里三段的标题（hook 按标题找段落） | In progress / Queue / Done |
| `shared_files` | 共享文件：不认领、只按锚点追加（写进规则） | 空 |
| `code_repos` | 开局要打印 worktree 的代码仓（相对或绝对路径） | 空 |
| `stale_hours` / `dead_hours` | 超过多久算闲置（独占失效）/ 超过多久清行 | 2 / 24 |
| `limits` | 在飞上限、重道上限、上下文软线 / 硬线（k）、启动卡阈值（分钟）、CLAUDE.md 字数预算 | 3 / 1 / 150 / 200 / 15 / 15000 |
| `timesheet` | 与 `scripts/timesheet` 联动（收工投递 note，不各自停钟） | false |

## 来历

- 2026-09-06 CAPP 一周复盘提出 SESSIONS 表 + hook + inbox；
- 09-08 定「一个 session 一行」；
- 09-10 起设控制塔岗；
- 09-16 起用跨 session 消息派单；
- 09-19 在 Vault session 里做了评估，抽出本通用版。只收骨架，CAPP 的事故补丁规则没有带过来；其中四条失效模式改成了脚本检查或规则片段里的一句话：CLAUDE.md 预算警告、上下文实测、部署侧依赖、付费调用存盘。
