# Changelog / 更新日志

All notable changes to this skill are documented in this file.
本文件记录本技能所有重要变更。

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).
格式参考 Keep a Changelog，版本号遵循语义化版本（SemVer）。

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
