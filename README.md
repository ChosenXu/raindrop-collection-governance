# Raindrop Collection Governance

English | [简体中文](README.zh-CN.md)

An [Agent Skills](https://agentskills.io)-compatible skill: **govern the collection (folder) structure of a [Raindrop.io](https://raindrop.io/) library** — read-only audits, user-confirmed restructuring, and misplaced-bookmark relocation. Works in any agent that reads the Agent Skills standard (Claude Code, Codex CLI, Gemini CLI, GitHub Copilot, Cursor, WorkBuddy…).

## What it does

Three phases, all write-gated:

1. **Audit (read-only)** — deterministic scan of the whole library: duplicate collection names, fragmented / empty collections, unsorted backlog, naming inconsistencies, misfiled hierarchy. Output is a P0/P1/P2 report with machine-checkable evidence (collection ids, parent chains).
2. **Restructure (confirmed)** — create / rename / re-parent / merge collections and move bookmarks, executed only after you confirm an operation plan. Every batch is snapshotted to an undo file and read back for verification.
3. **Relocate** — find bookmarks stored in the wrong collection (Pro semantic diagnostics, or a tag/domain/title heuristic on the free plan) and move them through the same confirmation gate.

A deeper **framework-review mode** assesses the overall taxonomy: classification-axis mixing, granularity balance, semantically overlapping collection pairs, and extensibility warnings (e.g. flat top-level collections past the split threshold).

Reports are rendered in the language you asked in (Simplified Chinese or English, strictly monolingual) and are always written to `/tmp/` — never into the library or the repo.

## Install

Clone this repository into your agent's skills directory:

| Agent | User-level directory | Project-level directory |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` | — |

Tip: `~/.agents/skills/` is the cross-agent directory — Codex CLI, Gemini CLI, GitHub Copilot, and Cursor read it natively, and Claude Code scans it as a fallback too. One install, discovered by multiple agents.

```bash
git clone https://github.com/ChosenXu/raindrop-collection-governance.git \
  ~/.agents/skills/raindrop-collection-governance
```

Or copy the folder manually into any of the directories above.

## Prerequisites

- **Raindrop.io MCP server** connected to your account — all reads and writes go through MCP. The official Raindrop MCP endpoint is `https://api.raindrop.io/rest/v2/ai/mcp` (Bearer token; get a test token at [app.raindrop.io/settings/integrations](https://app.raindrop.io/settings/integrations) → **For Developers** → Test tokens, and never commit it anywhere).

Example `mcpServers` entry (JSON-based agents):

```json
{
  "mcpServers": {
    "raindrop": {
      "url": "https://api.raindrop.io/rest/v2/ai/mcp",
      "headers": { "Authorization": "Bearer <your-token>" }
    }
  }
}
```

Where to put the MCP configuration per agent:

| Agent | MCP configuration location |
|---|---|
| Claude Code | `claude mcp add` (user scope) or project `.mcp.json` |
| Codex CLI | `~/.codex/config.toml` → `[mcp_servers.raindrop]` (TOML syntax) |
| Gemini CLI | `~/.gemini/settings.json` → `mcpServers` |
| GitHub Copilot | `~/.copilot/mcp-config.json` (or repo-root `.mcp.json`) |
| Cursor | `~/.cursor/mcp.json` |
| WorkBuddy | `~/.workbuddy/mcp.json` → `mcpServers` |

Notes: Codex CLI uses TOML, all others use JSON. Remote (URL-based) MCP servers need `url` + `headers` fields where the agent supports them; if your agent only supports stdio servers, wrap the remote endpoint with an MCP proxy.

- **Free-plan caveat**: semantic search parameters and `find_misplaced_bookmarks` are Pro-gated. This skill never depends on them — relocation works with the built-in tag/domain/title heuristic on free plans.
- **Optional REST fallback**: a test token exportable as `export RD_API_TOKEN=<your-token>` (documented; not implemented in scripts yet).

## Usage

Mention Raindrop with an intent like "audit my Raindrop collections" / "盘点一下收藏夹" / "重组收藏夹结构" / "framework review 收藏夹框架", and the skill drives the three-phase workflow. The audit engine is also usable standalone:

```bash
# collection-level audit report (P0/P1/P2)
python3 scripts/audit.py --collections dump.json --unsorted unsorted.json \
  --lang zh --out /tmp/audit-report.md

# framework review (top-level structure metrics)
python3 scripts/audit.py --mode framework --collections dump.json \
  --lang auto --sample "评审一下收藏夹框架" --out /tmp/framework-report.md

# regression suite
python3 -m unittest discover -s tests -v
```

`dump.json` is the output of Raindrop's `find_collections` MCP call; `--lang auto` detects the report language from `--sample` (CJK ratio, English fallback).

## Safety

- **Never deletes bookmarks or collections** — consolidation goes through `merge_collections`, never `delete_collections` / `delete_bookmarks`.
- **Never edits bookmark metadata** (title / note / tags) — this skill owns where bookmarks live; [raindrop-bookmark-organizer](https://github.com/ChosenXu/raindrop-bookmark-organizer) owns what they look like.
- **No write without a confirmed plan** — operation list first (object, action, risk, rollback), one confirmation per batch, ≤10 operations per batch.
- **Snapshot before write, readback after write** — success counters are never trusted alone; every report distinguishes `requested / verified_ok / UNVERIFIED`.

## Structure

```
SKILL.md                            # skill definition & workflow
README.md                           # this file
LICENSE                             # MIT
docs/
  decisions.md                      # architecture decisions & rationale
references/
  audit-rules.md                    # detection rules R1-R10 + FR1-FR5, report formats
scripts/
  audit.py                          # deterministic audit & framework report renderer
tests/
  test_audit.py                     # stdlib regression suite
```

## License

[MIT](LICENSE)
