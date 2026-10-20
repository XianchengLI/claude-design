---
name: judge-bundle
description: 把需要 Claude 逐条判断的活打成自包含的判断包（tower kit 通用版），交给干净 session 或子 agent 用 /judge-bundle-run 执行，结果由脚本回流。项目根有 tower.json 时，凡是要 Claude 当判官（评回答、比两版、判事实冲突、校准打标），或用户说 /judge-bundle、打包给新 session 判时使用。工作 session 只打包，不判。
user-invocable: true
allowed-tools: [Bash, Read, Write, Edit, Glob]
---

# /judge-bundle — 打判断包（工作 session 侧）

为什么要这样做：判断材料一进工作 session，就会污染上下文、烧掉限额，而且事后无法复盘「判官当时看到了什么」。所以工作 session 只打包，判断在干净上下文里做，工作 session 只看回流的数字。
包目录：`tower.json` 的 `files.judge_dir`（默认 `data/judge_bundles/`）下的 `<YYYY-MM-DD>_<topic>/`。

## 包结构

```
<judge_dir>/<date>_<topic>/
├── README.md       任务卡：判官只读它和 rubric.md 就知道要做什么
├── rubric.md       判什么 / 不判什么 / 每个结论的定义 / 背景事实 / 常见误判
├── input/packet_<k>.json   每包 ≤ 20 条，自包含（材料 + 被判对象 + 判断所需事实 + 代码能预算的提示）
├── output/         判官写：result_<k>.json + summary.md（打包时是空目录）
├── merge.py        回流：读 output/，出汇总或指标，写回项目该去的地方
└── _blind_map.json 盲化钥匙（对照类包才有，任务卡列为禁读）
```

## 红线

- **材料不进本 session 上下文。** 切包、预计算、写 README 全部用脚本完成；不 cat、不 Read 任何回答文本或 packet，只打印包数、条数和 id。
- **对照类包必须盲化，而且键序也不能泄露分组**：各臂的回答写成 X / Y / Z，臂到槽的映射逐条随机（三臂用全排列），JSON 按槽名排序输出。建包后验证每个臂在各槽的分布没有固定槽位。
- **防倒退的对照要带第三格「同配置重跑」**，作为噪声底。温度 0 也不保证确定：同配置重跑的判定会翻档，措辞每次都变。merge.py 把 REGRESSED 和 NOISE FLOOR 并排输出，放行三档：REGRESSED = 0 放行；0 < REGRESSED ≤ NOISE FLOOR 与噪声不可分，要逐条读；> NOISE FLOOR 视为倒退。
- 文本相似度不能代替判读。

## 步骤

1. **定问题与边界**（写进任务卡）：这次判断回答什么问题；判什么，**明确不判什么**；每个结论的定义。
2. **写 builder 脚本**：读运行产物 → 每条组成 item → 切包 → 写 `input/`、`README.md`、`rubric.md`、`merge.py`，建好空的 `output/`。
3. **跑 builder**，只看它打印的包数、条数和 id。
4. **认领**：在 SESSIONS 行只认领 `<包>/input/`、`README.md`、`rubric.md`，**不要认领整个包目录**，`output/` 归判官（认领整目录会让判官的写入被 hook 挡回）。
5. **告诉用户**：包路径；在新 session 里跑 `/judge-bundle-run <路径>`，或由本 session 派一个干净子 agent 执行（子 agent 只读 README / rubric / 包本身、不带本 session 上下文、判官模型不降档）；预计包数、每包 token、建议模型；判完回来跑 `python <包>/merge.py`。

## 任务卡 README 模板

```markdown
# <topic> · 判断任务卡
目的 / 结果给谁用：
边界：判 … ；不判 …
输入：input/packet_<k>.json，每条字段：…（哪些是材料、哪些是被判对象、哪些是预算提示）
输出：output/result_<k>.json，每条 {"id", …, "confidence", "note"}；枚举值定义；confidence 的写法（三档或 0–1，二选一写死）
口径：见 rubric.md；无法判定时写 …
执行：共 N 包；子 agent 最多两个并行；判断用当前模型，不用便宜档；每包约 X 万 token
禁止：不读包外文件、不联网、不猜模型动机、不改 input；_blind_map.json 禁读
回流：判完在工作 session 跑 `python <包>/merge.py`
```

## 完成标准

`input/` 有包，README / rubric / merge.py 齐全，`output/` 为空；本 session 上下文里没有出现任何一条被判材料的原文。
