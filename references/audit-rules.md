# Audit Rules

Detection rules for the collection-structure audit. Every rule produces a finding with: evidence (collection ids, parent chain, counts), a priority, and a suggested operation type. The audit script (`scripts/audit.py`) implements these rules deterministically; this document is the specification.

Exclusions: `Unsorted` (id -1) and `Trash` (id -99) are never flagged as fragmented or empty. Unsorted backlog is its own rule.

## Priority criteria

| Priority | Meaning | Examples |
|---|---|---|
| P0 | Causes wrong saves or blocks daily use now | duplicate titles under the same parent; Unsorted backlog > 20 |
| P1 | Structural friction that compounds over time | cross-parent duplicate titles, empty collections, fragmented collections, orphans, hollow top-level containers |
| P2 | Polish; fix when convenient | singular/plural pairs, language mix, casing conflicts, over-deep hierarchy |

## Detection rules

### R1 — Duplicate titles (by title, case-insensitive)

Group all non-excluded collections by normalized title (`strip().lower()`).

- Same title under the **same parent** → **P0**. Ambiguous targets for quick-save and drag-drop; one must be renamed or the pair merged.
- Same title under **different parents** → **P1**. Legitimate in some trees, but breaks search and quick-save disambiguation; recommend renaming to distinguish (e.g. `Code/Study` → `Study-Code`) or merging if themes overlap.

### R2 — Fragmented collections

`bookmarks_count <= 5` (direct, not total) → **P2** merge candidate. Present count and parent chain; never merge without user confirmation. Deliberate small buckets (e.g. temporary or watch-later style) are the user's call — the report only flags.

### R3 — Empty collections

`bookmarks_count == 0` (and no children) → **P1**. Suggest delete-via-user (user does it in the app) or repurposing. This skill never calls `delete_collections`; the recommendation is informational unless the user asks for a merge into another collection.

### R4 — Hollow top-level containers

Top-level collection with `bookmarks_count == 0..2` but `total_bookmarks_count` carried by children → **P2, informational**. A pure container is acceptable; flag only so the user notices. No action suggested by default.

### R5 — Unsorted backlog

Count of bookmarks in `Unsorted` (id -1):

- > 20 → **P0**
- 1–20 → **P1**

Report titles + domains (up to 30 rows, then summary). Suggestion: batch-assign to collections, optionally reusing `raindrop-bookmark-organizer` for metadata first.

### R6 — Singular/plural title pairs

Two distinct titles normalize to the same string after `lower()` + strip trailing `s` (e.g. `Tool`/`Tools`, `Product`/`Products`) → **P1**. Recommend one canonical form; if both exist with content, treat as R1 duplicates after the user picks the canonical form.

### R7 — Language mix

Detect CJK characters in titles. If ≥ 80% of titles are ASCII (dominant style) and some contain CJK → **P2** on the CJK ones. If the library is genuinely bilingual, the report says so and suggests a per-subtree language convention instead of renames.

### R8 — Casing conflicts

Titles differing only by case (`design` vs `Design`) → **P1**, same handling as R1.

### R9 — Orphaned / broken hierarchy

`parent_id` referencing a nonexistent collection → **P1**, evidence shows the orphan and the missing id. Suggest re-parenting.

### R10 — Over-deep hierarchy

Depth > 3 (top-level = depth 1) → **P2** per affected collection. Suggest flattening one level.

## Report format

`audit.py` renders Markdown with these sections, in order:

1. **Overview** — total collections / bookmarks / tags, top-level count, max depth, Unsorted count
2. **P0 findings** — table: finding, evidence (ids + parent chain), suggested operation, priority
3. **P1 findings** — same table shape
4. **P2 findings** — same table shape
5. **Operation summary** — counts per operation type (merge / rename / re-parent / create / move-bookmarks), ready to be turned into a Phase 2 plan

Every finding row carries machine-checkable evidence (collection ids) so the Phase 2 plan can reference exactly the same objects.
