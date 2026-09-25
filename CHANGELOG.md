# Changelog / 更新日志

All notable changes to this skill are documented in this file.
本文件记录本技能所有重要变更。

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).
格式参考 Keep a Changelog，版本号遵循语义化版本（SemVer）。

## [1.2.2] - 2026-09-25

### Fixed / 修复

- `jev_precheck.py` now validates `--workers` (1–32) and the confidence thresholds (`0 < medium < high <= 1`) up front with a clear argparse error, instead of crashing later inside `ThreadPoolExecutor` or silently producing meaningless bands.
  `jev_precheck.py` 启动时即校验 `--workers`（1–32）与置信阈值（`0 < medium < high <= 1`），给出明确的 argparse 报错；不再等到 `ThreadPoolExecutor` 内部崩溃，也不会静默产出无意义的分档。
- `audit.py` no longer crashes with a bare `KeyError` when a collection record is missing its `title` field — all title reads are now null-safe (empty title renders as blank); R7's old `or ""` guard covered `null` but not a missing key.
  `audit.py` 在收藏夹记录缺少 `title` 字段时不再裸抛 `KeyError`——所有标题读取改为空值安全（缺失标题渲染为空）；R7 原有的 `or ""` 防护只覆盖 `null` 值、不覆盖缺字段。

### Changed / 变更

- R3's has-children check now uses a precomputed parent-id set and R6's singular/plural scan stores members directly in the grouping dict, removing two O(n²) full-list scans in `audit()`.
  R3 的子夹判断改为使用预计算的父级 id 集合，R6 的单复数扫描改为在分组字典中直存成员，消除 `audit()` 中两处 O(n²) 全量扫描。
- Two regression tests added: missing-`title` robustness (audit) and CLI argument validation (jev_precheck); suite is now 21 tests.
  新增两项回归测试：缺 `title` 容错（audit）与命令行参数校验（jev_precheck）；测试套件现为 21 项。

### Notes / 说明

- Version bumped 1.2.1 → 1.2.2 (PATCH: robustness fixes and internal performance cleanups only; audit findings and report output are unchanged for well-formed input).
  版本 1.2.1 → 1.2.2（PATCH：仅健壮性修复与内部性能清理；对格式完好的输入，审计发现与报告输出完全不变）。

## [1.2.1] - 2026-09-24

### Fixed / 修复

- `jev_precheck.py` failure verdicts now go to stdout (plus exit code 1) instead of stderr — callers parsing stdout always see the reason JSON.
  `jev_precheck.py` 的失败结论改为输出到 stdout（并返回退出码 1），不再走 stderr——解析 stdout 的调用方一定能拿到原因 JSON。
- Hardened network behavior: every Jev call now carries an explicit 30 s timeout (SDK default 10 s was tight for large criteria sets), and each bookmark gets a 300 s hard cap across all its calls, recorded as an error instead of stalling the run. The SDK's built-in 429/5xx retry (3 attempts) is relied on rather than duplicated.
  加固网络行为：每次 Jev 调用显式设置 30 秒超时（SDK 默认 10 秒对大选项集偏紧），每个书签在全部调用上设 300 秒硬上限，超时记为错误条目而不再卡住整轮；429/5xx 重试直接复用 SDK 内置的 3 次重试，不另造一层。
- Each worker thread now uses its own `TypeSafeClient` instance (thread-local) — the SDK does not document thread safety, so client instances are no longer shared across the thread pool.
  每个工作线程改用各自的 `TypeSafeClient` 实例（线程本地存储）——SDK 未声明线程安全，客户端实例不再跨线程池共享。

### Changed / 变更

- Install docs now pin `typesafe-sdk>=0.7.0,<0.8` (verified against 0.7.0) in the script docstring and SKILL.md, guarding against breaking or unvetted SDK updates; removed an unused `as_completed` import.
  安装说明在脚本文档字符串与 SKILL.md 中锁定 `typesafe-sdk>=0.7.0,<0.8`（已对 0.7.0 验证），防范破坏性或未经验证的 SDK 更新；顺带移除未使用的 `as_completed` 导入。

### Notes / 说明

- Version bumped 1.2.0 → 1.2.1 (PATCH: robustness and safety fixes only; no feature or output-format changes beyond the stderr→stdout fix above).
  版本 1.2.0 → 1.2.1（PATCH：仅健壮性与安全性修复；除上述 stderr→stdout 修正外无功能或输出格式变化）。

## [1.2.0] - 2026-09-21

### Changed / 变更

- The Jev pre-screener now auto-enables when the environment is ready (API key + importable SDK + Python ≥3.10, verified by one tiny probe call) — no manual step. Its candidates are merged with the heuristic findings and labeled by source (`jev` / `heuristic` / `both`).
  环境就绪时 Jev 预筛器自动启用（API key + 可导入的 SDK + Python ≥3.10，经一次微型探针调用核验）——无需手动操作；候选与启发式结果合并并标注来源（`jev` / `heuristic` / `both`）。
- Mid-run failures keep completed items and hand the failed bookmark ids back to the heuristic instead of losing them.
  跑批中途失败时保留已完成项，并把失败的书签 id 交回启发式补齐，不再丢失。
- New opt-out switch `RAINDROP_GOV_JEV=off` restores the pre-auto behavior entirely; new `--probe` / `--probe-call` modes expose the environment verdict as JSON.
  新增关闭开关 `RAINDROP_GOV_JEV=off`（完全恢复自动启用前的行为）；新增 `--probe` / `--probe-call` 探测模式，以 JSON 输出环境结论。

### Notes / 说明

- Version bumped 1.1.0 → 1.2.0 (MINOR: behavior change — auto-enable when detected; environments without Jev behave exactly as before).
  版本 1.1.0 → 1.2.0（MINOR：行为变更——检测到即自动启用；无 Jev 的环境与之前完全一致）。

## [1.1.0] - 2026-09-21

### Added / 新增

- Optional Jev pre-screener (`scripts/jev_precheck.py`): blind-classifies bookmarks against user-defined categories and outputs relocation candidates with confidence bands (high ≥0.85 / medium ≥0.50 / low discarded). Flat mode validated on a 58-bookmark labeled exam — all 8 known misfiled bookmarks flagged and routed correctly (confidence 0.79–1.00); tree-descent mode ships as experimental.
  可选 Jev 预筛器（`scripts/jev_precheck.py`）：将书签对使用者定义的类别做盲分类，输出带置信分档（高 ≥0.85 / 中 ≥0.50 / 低丢弃）的归位候选。flat 模式经 58 条标注考卷验证——8/8 已知错位书签全部标记并正确路由（置信 0.79–1.00）；树下降模式为实验性。
- Privacy disclosure in SKILL.md: the pre-screener sends bookmark titles/tags/domains to the third-party TypeSafe API; the heuristic path remains the default and works fully offline.
  SKILL.md 增补隐私说明：预筛器会将书签标题/标签/域名发送给第三方 TypeSafe API；启发式路径仍为默认，完全可离线。

### Notes / 说明

- Version bumped 1.0.1 → 1.1.0 (MINOR: new optional capability); default behavior unchanged.
  版本 1.0.1 → 1.1.0（MINOR：新增可选能力）；默认行为无任何变化。

## [1.0.1] - 2026-09-17

### Added / 新增

- Bilingual `CHANGELOG.md` covering the full 0.1.0 → 1.0.0 history.
  新增双语 `CHANGELOG.md`，完整记录 0.1.0 → 1.0.0 历史。

### Notes / 说明

- Version bumped 1.0.0 → 1.0.1 (PATCH: documentation only); no workflow or write-behavior changes.
  版本 1.0.0 → 1.0.1（PATCH：纯文档）；工作流与写入行为无任何变化。

## [1.0.0] - 2026-09-17

First public release. Battle-tested on a real 1,101-bookmark library: 60+ bookmarks relocated, 6 collections renamed, a full framework review executed — zero data loss.
首个公开发布版本。在真实的 1101 条书签库上实测：60+ 书签归位、6 个收藏夹改名、完整框架评审执行——零数据丢失。

### Added / 新增

- Three-phase governance workflow: read-only audit → user-confirmed restructuring → misplaced-bookmark relocation, with undo snapshots, readback verification and checkpointed worklogs.
  三阶段治理工作流：只读盘点 → 经确认的重组 → 放错书签归位，含回滚快照、回读验证与检查点日志。
- Deterministic audit engine (`scripts/audit.py`): rules R1–R10 — duplicate names, fragmented/empty collections, unsorted backlog, singular/plural, language mix, casing, orphans, over-deep hierarchy — with P0/P1/P2 classification.
  确定性盘点引擎（`scripts/audit.py`）：规则 R1–R10——重名、碎片/空夹、未分类积压、单复数、语言混用、大小写、孤级、超深层级——按 P0/P1/P2 分级。
- Framework-review mode (`--mode framework`): FR1–FR3 deterministic metrics (flat-heavy, dominance, tiny top-levels) plus FR4–FR5 agent-layer semantics (overlapping pairs, classification-axis mixing).
  框架评审模式（`--mode framework`）：FR1–FR3 确定性指标（平铺大夹、体量失衡、微型顶层）+ FR4–FR5 语义层（重叠夹对、分类轴混用）。
- Language-adaptive reports: `--lang auto/zh/en` with CJK-ratio detection and English fallback; a bilingual string table makes every report monolingual by construction.
  语言自适应报告：`--lang auto/zh/en` 中日韩占比检测、无样本兜底英文；双语字串表使每份报告由结构保证单语。
- Bilingual README (English / 简体中文), MIT license, and a 14-test regression suite.
  双语 README（英文 / 简体中文）、MIT 许可证、14 项回归测试。

### Safety / 安全

- Never deletes bookmarks or collections; never edits bookmark metadata (title / note / tags); no write without a confirmed plan; every batch is snapshotted and read back verified.
  绝不删除书签或收藏夹；绝不修改书签元数据（标题 / 描述 / 标签）；无确认不写入；每批操作先快照、后回读验证。

## [0.3.3] - 2026-09-17

### Added / 新增

- Simplified Chinese README (`README.zh-CN.md`); language switcher on the English README.
  新增简体中文 README（`README.zh-CN.md`）；英文 README 加双语切换行。

## [0.3.2] - 2026-09-17

### Added / 新增

- `tests/test_audit.py` — 14-case stdlib regression suite covering R1–R6, language detection, monolingual rendering and FR1–FR3.
  `tests/test_audit.py`——14 用例标准库回归测试，覆盖 R1–R6、语言检测、单语渲染与 FR1–FR3。
- Release preparation: English README, MIT `LICENSE`, description compressed to ≤500 characters.
  发布前置：英文 README、MIT `LICENSE`、描述压缩至 ≤500 字符。

### Changed / 变更

- Phase 2 documents the merge-rollback rule: a re-created source collection gets a new collection id; the old id in the undo file is a record only.
  第二阶段补充合并回滚规则：重建的源收藏夹会获得新 id；回滚文件中的旧 id 仅作记录。

## [0.3.1] - 2026-09-16

### Changed / 变更

- Removed version annotations from skill body text; added the tool-family rule (collection tools and the bookmark tool are never mixed in one call) and the worklog JSONL schema.
  清理正文中的版本标注；新增工具族规则（收藏夹工具与书签工具不得在同一次调用中混用）与 worklog JSONL 行格式。
- `references/audit-rules.md` gains the framework report format spec (deterministic + semantic sections).
  `references/audit-rules.md` 补充框架报告格式规格（确定性层 + 语义层分节）。

## [0.3.0] - 2026-09-15

### Added / 新增

- Framework-review mode (`--mode framework`): FR1–FR3 deterministic (flat-heavy, dominance, tiny top-levels) and FR4–FR5 agent-layer semantics; decision record D10.
  框架评审模式（`--mode framework`）：FR1–FR3 确定性指标（平铺大夹、体量失衡、微型顶层）与 FR4–FR5 语义层；决策记录 D10。

## [0.2.0] - 2026-09-15

### Added / 新增

- Language-adaptive reports: `--lang auto/zh/en` + `--sample` (CJK-ratio detection, English fallback); all report strings moved into a bilingual table so a report is monolingual by construction.
  语言自适应报告：`--lang auto/zh/en` + `--sample`（中日韩占比检测，无样本兜底英文）；全部报告文案迁入双语字串表，单语由结构保证。

### Fixed / 修复

- Priority-heading spacing (`P0发现` → `P0 发现`); pycache build artifacts excluded from git tracking via `.gitignore`.
  优先级标题缺空格（`P0发现` → `P0 发现`）；`.gitignore` 排除 pycache 构建产物。

## [0.1.0] - 2026-09-15

Initial version: three-phase workflow, safety hard rules (no bookmark deletion, no metadata edits, confirmation-gated writes, readback verification), audit rules R1–R10, decision records D1–D8.
初始版本：三阶段工作流、安全硬规则（不删书签、不改元数据、确认闸口写入、回读验证）、盘点规则 R1–R10、决策记录 D1–D8。

### Added / 新增

- `SKILL.md`, `references/audit-rules.md`, `scripts/audit.py`, `docs/decisions.md`.
- `SKILL.md`、`references/audit-rules.md`、`scripts/audit.py`、`docs/decisions.md`。
