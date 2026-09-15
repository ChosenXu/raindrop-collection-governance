---
name: raindrop-collection-governance
description: Use when the user wants to audit, restructure, or govern the collection structure of their Raindrop.io library (via the Raindrop MCP server, REST fallback). Triggers on Raindrop, raindrop.io, 收藏夹, collections, folders combined with a governance intent (盘点 / 体检 / 重组 / 合并 / 挪书签 / audit / restructure / merge / consolidate). Three-phase workflow: read-only audit with P0/P1/P2 findings, user-confirmed restructuring with rollback snapshots and readback verification, misplaced-bookmark relocation with a free-plan heuristic fallback. Never touches bookmark titles, notes, or tags — that is raindrop-bookmark-organizer's domain.
agent_created: true
version: 0.1.0
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
| Raindrop REST API v1 (`api.raindrop.io/rest/v1/...`, token in `env RD_API_TOKEN`) | documented fallback only, not implemented in 0.1.0 |

Free-plan constraint: semantic search parameters and `find_misplaced_bookmarks` are Pro-gated. Never rely on them as the only path — the relocation phase must work with the heuristic described below.

## Safety rules (hard)

- **Never delete bookmarks.** `delete_bookmarks` and `delete_collections` are never called. Consolidation uses `merge_collections` (bookmarks move into the target; source collections are removed) — never `delete_collections` (bookmarks go to Trash).
- **Never touch bookmark title / note / tags.** The only bookmark-level write is `collection_id` (moving).
- **No write without a confirmed plan.** Phase 2 renders an operation list (object, action, risk, rollback). Execution starts only after the user explicitly confirms that list. One confirmation per batch.
- **Snapshot before write.** Before the first write of a session, save the affected collections' state (id, title, parent_id) and affected bookmark→collection mappings to an undo file in `/tmp/`.
- **Verify every write.** After each batch, read back the affected objects and report `requested / verified_ok`. Never trust success counters alone (Raindrop APIs have lied before — e.g. `delete_tags` reports success for nonexistent tags).
- **Small batches.** ≤10 operations per batch; stop on first failure and report.
- **All reports and runtime data go to `/tmp/`**, never into the skill folder or any repo.

## Workflow

### Phase 1 — Audit (read-only)

1. Collect: `find_collections` (full list, includes per-collection counts), `fetch_current_user` (library stats), `find_bookmarks` with `collection_ids: [-1]` (Unsorted backlog details).
2. Save raw JSON dumps to `/tmp/raindrop-gov-<date>/`.
3. Run `python3 scripts/audit.py --collections <dump> [--unsorted <dump>] --out <report.md>` — deterministic classification per `references/audit-rules.md`. Python 3.9+, stdlib only.
4. Present the report: findings table with evidence (ids, parent chains), P0/P1/P2 recommendations, each mapped to an operation type.
5. **Stop here.** No writes happen in Phase 1. Wait for the user to pick items.

### Phase 2 — Plan & confirm (hard gate)

For every user-approved finding, render an operation plan:

| Field | Example |
|---|---|
| Operation | merge / rename / re-parent / create / move-bookmarks |
| Object | `Study` (53504999) → target `Study` (53467378) |
| Risk | source collection is removed; bookmarks stay |
| Rollback | recreate source, move bookmarks back (undo file) |

Order of execution once confirmed: **create → rename → re-parent → move bookmarks → merge (always last, it deletes sources)**.

### Phase 3 — Execute & verify

1. Write the undo snapshot to `/tmp/`.
2. Execute in the order above, batches ≤10, readback verification after each batch (`find_collections` / `find_bookmarks`).
3. Append a JSONL checkpoint after every batch (`/tmp/raindrop-gov-<date>/worklog.jsonl`) so a session can resume.
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
