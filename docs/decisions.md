# Architecture Decisions

Rationale for the structural choices in this skill. Each decision states the choice, the reason, and the rejected alternatives where relevant.

## D1 — Raindrop MCP as the primary channel

All reads (`find_collections`, `find_bookmarks`, `fetch_current_user`), all writes (`create_collections`, `update_collections`, `merge_collections`, `update_bookmarks`), and readback verification are available as MCP tools, including batch limits (150 per call) that match the batch discipline. The REST API v1 remains the documented fallback but is not implemented: no client script exists until a real MCP outage forces one. Rejected: REST-first like `raindrop-bookmark-organizer` — that skill needed write verification the MCP of the time did not expose; this skill's workload fits MCP directly.

## D2 — Deterministic audit script instead of model judgment

Classification (duplicate groups, fragmentation, empties, naming conflicts) is string/set logic with fixed thresholds. A script gives reproducible findings with machine-checkable evidence (collection ids), so the Phase 2 plan can reference exactly the same objects across sessions. Model judgment is reserved for what scripts cannot do: judging whether two fragmented collections share a theme. The thresholds and rules live in `references/audit-rules.md`; the script implements that spec.

## D3 — Merge instead of delete, everywhere

`delete_collections` moves bookmarks to Trash and is never called. Consolidation goes through `merge_collections`, which moves all source bookmarks into the target before removing the sources. The residual risk (a merge is hard to undo when the source had a long parent chain) is covered by the undo snapshot and per-batch confirmation, not by keeping the delete path around.

## D4 — Confirmation gate per batch, snapshot before first write

Every write session renders an operation plan (operation, object, risk, rollback) and waits for explicit user confirmation of that exact list. Before the first write, the affected state is snapshotted to `/tmp/` as an undo mapping. This follows the workspace-wide rule that destructive-capable operations require listed objects, impact, and rollback before execution.

## D5 — Readback verification over success counters

Raindrop APIs have reported success for operations that did not happen (observed with `delete_tags` in the sibling skill). Every batch is followed by a readback of the affected objects; the report distinguishes `requested / verified_ok / UNVERIFIED` and never treats a counter alone as proof.

## D6 — Reports and runtime data stay out of the repository

Audit reports, JSON dumps, undo snapshots, and checkpoint worklogs are written to `/tmp/raindrop-gov-<date>/`. They are session artifacts, may contain library content, and must never be committed or synced.

## D7 — Free-plan heuristic for misplaced bookmarks

Semantic capabilities (`find_misplaced_bookmarks`, semantic search parameters) are Pro-gated. On the free plan, relocation candidates come from comparing each bookmark's tags / domain / title keywords against its collection's theme. A library where every bookmark is tagged gives the heuristic enough signal; candidates still go through the same confirmation gate as every other operation.

## D8 — Strict boundary with raindrop-bookmark-organizer

Organizer: bookmark metadata (title / note / tags), metadata-first classification, no collection moves. This skill: collection structure and bookmark location, no metadata edits. The only interface between them is organizer's optional "suggested target collection" output, which this skill can turn into executed moves. Keeping the boundary strict prevents both skills from writing the same fields.

## D9 — Report language follows the invocation language, detected at two layers

The report must be in the language the user asked in, and one report must never mix languages. Detection is layered: the agent workflow detects the invocation language (it sees the user's request directly) and passes `--lang` explicitly; the script additionally supports `--lang auto --sample "<request text>"` with a deterministic CJK-ratio check, so the behavior is reproducible and testable without trusting model judgment. Without any signal the report falls back to English, matching the workspace-wide convention that English is the pivot language. Library content (collection titles, tag names, URLs) is data, not prose — it stays verbatim in both languages. All report strings live in one bilingual table, which makes "one report, one language" structural rather than a per-sentence choice.

## D10 — Framework review is a hybrid: deterministic metrics plus agent semantics

The framework-review mode answers tree-level questions (is the taxonomy sound, where will structure break next) that the collection-level audit cannot see. It is deliberately split: the script computes what is objectively checkable (size distribution, flat-heavy thresholds, dominance ratio, tiny top-levels — FR1–FR3), giving reproducible numbers; the agent does what requires reading contents (taxonomy-axis identification, overlapping-pair detection, misfile candidates, boundary rules — FR4–FR5). The gate structure carries over unchanged: the framework report ends in recommendations, and every structural change still goes through Phase 2 confirmation. Default stance is conservative — a small focused collection is healthy, and fragmentation alone is never a merge reason; this was validated against a real library where all 14 fragmented collections turned out to be legitimate.

## D11 — Platform-convention paths are content, not defects

The package validator flags `~/.claude/skills/`, `/tmp/` and similar as `absolute_path` errors. In this skill those paths are subject matter: `~/.<agent>/skills/` is the install matrix every multi-platform skill must document, and `/tmp/raindrop-gov-<date>/` is the mandated report destination. Hardcoding a real user path (`/Users/<name>/…`) would be a defect; none exists in the package. The sibling repositories carry the same pattern and the same validator findings, so these findings are recorded as a known false-positive class instead of being "fixed" by removing the paths.

