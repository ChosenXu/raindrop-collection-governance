# Raindrop Collection Governance

[English](README.md) | 简体中文

一个兼容 [Agent Skills](https://agentskills.io) 标准的 skill：**治理 [Raindrop.io](https://raindrop.io/) 收藏库的收藏夹（文件夹）结构**——只读盘点、经确认后执行重组、放错书签归位。适用于任何支持 Agent Skills 标准的智能体（Claude Code、Codex CLI、Gemini CLI、GitHub Copilot、Cursor、WorkBuddy…）。

## 它做什么

三个阶段，全部有写入闸口：

1. **盘点（只读）**——对整个收藏库做确定性扫描：收藏夹重名、碎片夹 / 空夹、未分类积压、命名不一致、层级错挂。产出带机器可查证据（收藏夹 id、父子链）的 P0/P1/P2 报告。
2. **重组（经确认）**——建夹 / 改名 / 挪层级 / 合并收藏夹、跨夹移动书签；只有在你确认执行计划之后才动手。每个批次先快照到回滚文件，再逐条回读验证。
3. **归位**——找出放错收藏夹的书签（Pro 会员走语义诊断，免费版走标签 / 域名 / 标题启发式），走同一确认闸口后移动。

更进一步的**框架评审模式**评估整体分类法：分类轴混用、粒度均衡、语义重叠的收藏夹对、扩展性预警（例如超过拆分阈值的平铺顶层夹）。

报告以你提问的语言渲染（简体中文或英文，整份严格单语），始终写入 `/tmp/`——绝不进入收藏库或仓库。

## 安装

把本仓库克隆到你所用智能体的 skills 目录：

| 智能体 | 用户级目录 | 项目级目录 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` | — |

提示：`~/.agents/skills/` 是跨智能体目录——Codex CLI、Gemini CLI、GitHub Copilot 和 Cursor 原生读取它，Claude Code 也会兜底扫描。装一次，多个智能体发现。

```bash
git clone https://github.com/ChosenXu/raindrop-collection-governance.git \
  ~/.agents/skills/raindrop-collection-governance
```

也可以手动把文件夹复制到上表任意目录。

## 前置条件

- **连接到你账号的 Raindrop.io MCP 服务器**——所有读写都走 MCP。Raindrop 官方 MCP 端点为 `https://api.raindrop.io/rest/v2/ai/mcp`（Bearer 令牌；在 [app.raindrop.io/settings/integrations](https://app.raindrop.io/settings/integrations) → **For Developers** → Test tokens 获取测试令牌，切勿提交到任何仓库）。

`mcpServers` 配置示例（JSON 类智能体）：

```json
{
  "mcpServers": {
    "raindrop": {
      "url": "https://api.raindrop.io/rest/v2/ai/mcp",
      "headers": { "Authorization": "Bearer <你的令牌>" }
    }
  }
}
```

各智能体的 MCP 配置位置：

| 智能体 | MCP 配置位置 |
|---|---|
| Claude Code | `claude mcp add`（用户级）或项目 `.mcp.json` |
| Codex CLI | `~/.codex/config.toml` → `[mcp_servers.raindrop]`（TOML 语法） |
| Gemini CLI | `~/.gemini/settings.json` → `mcpServers` |
| GitHub Copilot | `~/.copilot/mcp-config.json`（或仓库根 `.mcp.json`） |
| Cursor | `~/.cursor/mcp.json` |
| WorkBuddy | `~/.workbuddy/mcp.json` → `mcpServers` |

说明：Codex CLI 用 TOML，其余用 JSON。远程（URL 型）MCP 服务器在支持的场景下使用 `url` + `headers` 字段；若你的智能体只支持 stdio 服务器，用 MCP 代理包裹该远程端点即可。

- **免费版注意**：语义搜索参数与 `find_misplaced_bookmarks` 为 Pro 会员功能。本 skill 从不依赖它们——归位在免费版下使用内置的标签 / 域名 / 标题启发式。
- **可选 REST 兜底**：测试令牌可以 `export RD_API_TOKEN=<你的令牌>` 导出（已写入文档；脚本尚未实现）。

## 使用

用一句带 Raindrop 的话触发即可，例如「盘点一下收藏夹」「重组收藏夹结构」「framework review 收藏夹框架」，skill 会驱动三阶段流程。盘点引擎也可以独立使用：

```bash
# 收藏夹级盘点报告（P0/P1/P2）
python3 scripts/audit.py --collections dump.json --unsorted unsorted.json \
  --lang zh --out /tmp/audit-report.md

# 框架评审（顶层结构指标）
python3 scripts/audit.py --mode framework --collections dump.json \
  --lang auto --sample "评审一下收藏夹框架" --out /tmp/framework-report.md

# 回归测试
python3 -m unittest discover -s tests -v
```

`dump.json` 是 Raindrop 的 `find_collections` MCP 调用输出；`--lang auto` 依据 `--sample` 检测报告语言（中日韩字符占比，无样本时兜底英文）。

## 安全边界

- **绝不删除书签或收藏夹**——合并走 `merge_collections`，从不调用 `delete_collections` / `delete_bookmarks`。
- **绝不修改书签元数据**（标题 / 描述 / 标签）——本 skill 管书签「住在哪里」；[raindrop-bookmark-organizer](https://github.com/ChosenXu/raindrop-bookmark-organizer) 管书签「长什么样」。
- **没有确认过的计划不写入**——先出操作清单（对象、动作、风险、回滚），每批一次确认，每批 ≤10 组操作。
- **写前快照、写后回读**——绝不单独轻信成功计数；每份报告都区分 `requested / verified_ok / UNVERIFIED`。

## 目录结构

```
SKILL.md                            # skill 定义与工作流
README.md                           # 本文件（英文 / 简体中文）
LICENSE                             # MIT
docs/
  decisions.md                      # 架构决策与理由
references/
  audit-rules.md                    # 检测规则 R1-R10 + FR1-FR5，报告格式
scripts/
  audit.py                          # 确定性盘点与框架评审报告渲染器
tests/
  test_audit.py                     # 标准库回归测试
```

## 许可证

[MIT](LICENSE)
