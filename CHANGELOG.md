# Changelog / 更新日志

All notable changes to this skill are documented in this file.
本文件记录本技能所有重要变更。

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).
格式参考 Keep a Changelog，版本号遵循语义化版本（SemVer）。

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
