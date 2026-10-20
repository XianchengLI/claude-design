---
name: judge-bundle-run
description: 在干净 session 或子 agent 里执行一个判断包（tower kit 通用版）：只读任务卡和口径，逐包判定，写 output/，最后报一行汇总。用户说 /judge-bundle-run <文件夹>、执行判断包、判这一包时使用。这是判断类任务，不用便宜模型。
user-invocable: true
allowed-tools: [Bash, Read, Write, Agent]
---

# /judge-bundle-run — 执行判断包（判官侧）

本 session 的全部工作就是判这个包，不做别的。

## 输入

`/judge-bundle-run <包路径>`。没给路径时，列出 `tower.json` 的 `files.judge_dir` 下 `output/` 还是空的包，让用户选。

## 步骤

1. **只读两份文件**：`README.md`（任务卡）和 `rubric.md`。包外的项目文件一律不读，不联网，`_blind_map.json` 不读。有 SESSIONS 表的项目，在自己那行认领 `<包>/output/`。
2. **续判检查**：`output/` 里已有的 `result_<k>.json`，先校验条数和 id 齐全，齐全的跳过，缺了才重判那一包。
3. **逐包判定**：≤ 2 包由本 session 直接判；> 2 包时每包派一个子 agent，**最多两个并行**（并发多了会撞会话限额）。子 agent 的 prompt = 「读 README 与 rubric，判 packet_k，按 README 的输出格式写 result_k.json，最后只回一行汇总」。判官用当前模型，不为省钱降档。
4. **每包写完即校验**：JSON 能解析；条数等于包内条数；id 一一对应；枚举取值合法（confidence 的写法以 README 为准）。不合格就重判该包。
5. **写 `output/summary.md`**：按格统计各枚举值的计数、有争议或无法判定的 id（各附一句原因）、rubric 疑似有错的地方（标「rubric 待改」）。
6. **最后回复只有一段**：汇总计数 + 争议点 + 「回工作 session 跑 `python <包>/merge.py`」。不复述被判材料。

## 判定纪律

- 只依据 packet 里的材料，packet 里没有的事实不能当判据（rubric 给的背景事实除外）。
- `note` 不超过 40 字；引用原文放 `claim` / `evidence` 字段，不整段复制。
- rubric 和材料冲突时以材料为准，并在 note 里标「rubric 待改」，不要让被判对象替测试集的错误背锅。
- 不改 `input/`，不改 README，结果只写 `output/`。
