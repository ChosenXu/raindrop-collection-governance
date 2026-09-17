---
name: raindrop-collection-governance
description: Use when the user wants to audit, restructure, or govern their Raindrop.io collection structure. Triggers on Raindrop, raindrop.io, 收藏夹, collections, folders with governance intent (盘点 / 体检 / 重组 / 合并 / 挪书签 / 框架评审 / audit / restructure / merge / framework review). Read-only P0/P1/P2 audit, confirmed restructuring with rollback and readback verification, misplaced-bookmark relocation, framework-review mode. Never edits bookmark titles, notes, or tags — raindrop-bookmark-organizer's domain.
agent_created: true
version: 1.0.0
license: MIT
---

# Raindrop Collection Governance

Govern the **collection (folder) structure** of a Raindrop.io library in three phases:

1. **盘点 (Audit)** — read-only scan, deterministic audit report with P0/P1/P2 findings
2. **重组 (Restructure)** — user-confirmed execution: create / rename / re-parent / merge collections, move bookmarks between collections
3. **归位 (Relocate)** — find bookmarks stored in the wrong collection and move them after confirmation

Division of labor: this skill owns **where bookmarks live** (structure). `raindrop-bookmark-organizer` owns **what bookmarks look like** (title / note / tags). This skill never edits bookmark metadata. Organizer's "suggested target collection" output can be executed by this skill.

## Architecture

| Channel | Used for |
|---|---|
| Raindrop MCP server (primary) | all reads, all writes, readback verification |
| Raindrop REST API v1 (`api.raindrop.io/rest/v1/...`, token in `env RD_API_TOKEN`) | documented fallback only, not implemented |

Free-plan constraint: semantic search parameters and `find_misplaced_bookmarks` are Pro-gated. Never rely on them as the only path — the relocation phase must work with the heuristic described below.

## Safety rules (hard)

- **Never delete bookmarks.** `delete_bookmarks` and `delete_collections` are never called. Consolidation uses `merge_collections` (bookmarks move into the target; source collections are removed) — never `delete_collections` (bookmarks go to Trash).
- **Never touch bookmark title / note / tags.** The only bookmark-level write is `collection_id` (moving).
- **No write without a confirmed plan.** Phase 2 renders an operation list (object, action, risk, rollback). Execution starts only after the user explicitly confirms that list. One confirmation per batch.
- **Snapshot before write.** Before the first write of a session, save the affected collections' state (id, title, parent_id) and affected bookmark→collection mappings to an undo file in `/tmp/`.
- **Verify every write.** After each batch, read back the affected objects and report `requested / verified_ok`. Never trust success counters alone (Raindrop APIs have lied before — e.g. `delete_tags` reports success for nonexistent tags).
- **Small batches.** ≤10 operations per batch; stop on first failure and report.
- **Use the right tool family.** Collection operations (create / rename / re-parent / merge) go through the collection tools (`create_collections` / `update_collections` / `merge_collections`); bookmark moves go through the bookmark tool (`update_bookmarks`). Never mix them in one call — the schemas differ and a mixed call fails validation before executing.
- **All reports and runtime data go to `/tmp/`**, never into the skill folder or any repo.

## Workflow

### Phase 1 — Audit (read-only)

1. Collect: `find_collections` (full list, includes per-collection counts), `fetch_current_user` (library stats), `find_bookmarks` with `collection_ids: [-1]` (Unsorted backlog details).
2. Save raw JSON dumps to `/tmp/raindrop-gov-<date>/`.
3. Detect the **user's invocation language** and pass it to the script: `--lang zh` / `--lang en`, or `--lang auto --sample "<the user's request text>"` (auto detects by CJK ratio, falls back to English without a sample). Run `python3 scripts/audit.py --collections <dump> [--unsorted <dump>] --out <report.md> ...` — deterministic classification per `references/audit-rules.md`. Python 3.9+, stdlib only. The rendered report is strictly monolingual; proper nouns, collection titles and URLs stay verbatim.
4. Present the report: findings table with evidence (ids, parent chains), P0/P1/P2 recommendations, each mapped to an operation type.
5. **Stop here.** No writes happen in Phase 1. Wait for the user to pick items.

### Framework review mode (on request)

Triggered by 框架评审 / 结构评审 / framework review / 评估整体结构. This is a deeper, tree-level assessment above the collection-level audit:

1. Run `python3 scripts/audit.py --mode framework --collections <dump> ...` (same `--lang` handling as above). The script produces the deterministic layer per `references/audit-rules.md` FR1–FR3: top-level size distribution, flat-heavy top-levels, size dominance, tiny top-levels.
2. The agent then performs the semantic layer, reading collection contents where needed:
   - **分类轴识别** — which classification logics (domain / content type / function / status) coexist at the top level, and where a new bookmark's placement would be ambiguous;
   - **语义重叠夹对** — collections whose contents answer the same "where do I save X?" question (compare actual contents, not just names; FR4);
   - **错位书签线索** — candidates found while reading, listed like any relocation candidate (goes through Phase 2 confirmation);
   - **扩展性预警** — flat collections approaching the point where retrieval degrades, with split proposals;
   - **边界规则建议** — one-sentence rules that disambiguate overlapping pairs (e.g. "News = content, Information = lookup tools").
3. Recommendations are conservative by default: a small focused collection is healthy, fragmentation alone is never a merge reason. Structural changes always go through the Phase 2 confirmation gate.
4. The report is strictly monolingual, following the invocation language (same `--lang` handling as the audit mode).

### Phase 2 — Plan & confirm (hard gate)

For every user-approved finding, render an operation plan:

| Field | Example |
|---|---|
| Operation | merge / rename / re-parent / create / move-bookmarks |
| Object | `Study` (53504999) → target `Study` (53467378) |
| Risk | source collection is removed; bookmarks stay |
| Rollback | recreate source, move bookmarks back (undo file) |

Order of execution once confirmed: **create → rename → re-parent → move bookmarks → merge (always last, it deletes sources)**.

Rollback note for merges: `merge_collections` removes the source collection, and a re-created source gets a **new collection id** — the original id recorded in the undo file is a record only. After a merge rollback, always reference the re-created id in all subsequent operations and verification.

### Phase 3 — Execute & verify

1. Write the undo snapshot to `/tmp/`.
2. Execute in the order above, batches ≤10, readback verification after each batch (`find_collections` / `find_bookmarks`).
3. Append a JSONL checkpoint after every batch (`/tmp/raindrop-gov-<date>/worklog.jsonl`) so a session can resume. One JSON object per line, fields: `ts` (ISO-ish timestamp), `phase` (e.g. `relocate-unsorted` / `dedup-renames` / `database-split`), `batch` (number or final summary marker), `ops` (operation count), `bookmarks` (bookmark count if applicable), `verified_ok` (readback-confirmed count), `undo_file` (snapshot path). Resume = read the last line, re-verify it, continue from the next unverified item.
4. Final pass: re-read all affected objects, diff against the plan, report `requested / verified_ok / UNVERIFIED` per operation. Final report to `/tmp/`.

### Relocating misplaced bookmarks (Phase 1 extension / standalone)

- Pro plan: `find_misplaced_bookmarks` over candidate collection ids, then verify each candidate manually.
- Free plan (heuristic): for each bookmark, compare its tags / domain / title keywords against the theme of its current collection. Flag mismatches as candidates. Never auto-move — candidates go through Phase 2 confirmation like any other operation.
- Cap candidate review at 150 per pass; paginate if needed.

## Supporting files

Load only when needed:

- `references/audit-rules.md` — detection rules and P0/P1/P2 criteria (load before Phase 1)
- `scripts/audit.py` — deterministic audit report renderer (Phase 1)
- `docs/decisions.md` — architecture decisions and rationale

## Out of scope (0.1.0)

- REST fallback client (documented, not implemented)
- Bookmark metadata editing (title / note / tags — organizer's domain)
- Highlight processing
- Automated / scheduled governance runs (every execution requires a live user confirmation)
