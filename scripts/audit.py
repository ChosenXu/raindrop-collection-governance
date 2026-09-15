#!/usr/bin/env python3
"""Deterministic audit report renderer for Raindrop collection governance.

Reads JSON dumps collected via the Raindrop MCP server (read-only) and renders
a Markdown audit report classified per references/audit-rules.md (R1-R10).

Usage:
    python3 audit.py --collections collections.json \
                     [--unsorted unsorted.json] \
                     [--user user.json] \
                     [--out report.md]

Input formats accepted (both a bare list and an MCP-shaped object work):
    collections.json : [{"collection_id":..., "title":..., "parent_id":...,
                         "bookmarks_count":..., "total_bookmarks_count":...}, ...]
                       or {"collections": [...]}
    unsorted.json    : [{"title":..., "domain":...}, ...] or {"bookmarks": [...]}
    user.json        : {"user": {"statistics": {...}}, ...}   (optional, overview only)

Reports go to /tmp/ (or --out); this script never writes inside the skill folder.
Stdlib only, Python 3.9+.
"""

import argparse
import json
import re
import sys

UNSORTED_ID = -1
TRASH_ID = -99
FRAGMENT_THRESHOLD = 5          # R2: bookmarks_count <= 5
UNSORTED_P0 = 20                # R5: > 20 -> P0
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
HOLLOW_TOP_DIRECT = 2           # R4: direct count <= 2 with children carrying content
MAX_DEPTH_OK = 3                # R10: depth > 3 is flagged


def load_records(path, list_key):
    """Return a list of dicts from a JSON dump (MCP-shaped object or bare list)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in (list_key, "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        # fetch_current_user style
        if "user" in data:
            return [data]
    raise SystemExit("error: %s does not contain a '%s' list" % (path, list_key))


def norm_title(title):
    return (title or "").strip().lower()


def singular_form(title):
    n = norm_title(title)
    return n[:-1] if n.endswith("s") and len(n) > 1 else n


def parent_chain(col, by_id):
    chain = []
    cur = col
    seen = set()
    while cur is not None and cur["collection_id"] not in seen:
        seen.add(cur["collection_id"])
        chain.append(cur["title"])
        pid = cur.get("parent_id")
        cur = by_id.get(pid) if pid is not None else None
    return " > ".join(reversed(chain))


def depth_of(col, by_id):
    d, cur, seen = 1, col, set()
    while True:
        pid = cur.get("parent_id")
        if pid is None or pid in seen:
            return d
        seen.add(pid)
        parent = by_id.get(pid)
        if parent is None:
            return d
        d += 1
        cur = parent


def finding(rule, priority, problem, evidence, suggestion, operation):
    return {
        "rule": rule,
        "priority": priority,
        "problem": problem,
        "evidence": evidence,
        "suggestion": suggestion,
        "operation": operation,
    }


def audit(collections, unsorted_items):
    by_id = {}
    for c in collections:
        cid = c.get("collection_id")
        if cid is not None:
            by_id[cid] = c
    governable = [c for c in collections
                  if c.get("collection_id") not in (UNSORTED_ID, TRASH_ID)]
    findings = []

    # R1 / R8 — duplicate titles (case-insensitive); R8 casing is a sub-case
    groups = {}
    casing = {}
    for c in governable:
        groups.setdefault(norm_title(c["title"]), []).append(c)
        casing.setdefault(c["title"], []).append(c)
    for n, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        parents = {m.get("parent_id") for m in members}
        chain_txt = "; ".join("%s (%s, in %s)" % (m["title"], m["collection_id"],
                                                  parent_chain(m, by_id) or "top level")
                              for m in members)
        if len(parents) == 1 and None not in parents:
            findings.append(finding(
                "R1", "P0", "Duplicate title under the same parent: %r x%d" % (members[0]["title"], len(members)),
                chain_txt,
                "Rename one, or merge the smaller into the larger",
                "merge-or-rename"))
        else:
            findings.append(finding(
                "R1", "P1", "Same title across different parents: %r x%d" % (members[0]["title"], len(members)),
                chain_txt,
                "Rename to disambiguate, or merge if themes overlap",
                "merge-or-rename"))
    for title, members in sorted(casing.items()):
        lowers = {norm_title(t) for t in casing}
        if len(members) == 1 and len(lowers) != len(casing):
            continue  # handled inside R1 groups; exact-case dupes are R1 already
    # exact-case duplicates (e.g. 'design' and 'Design')
    for n, members in groups.items():
        titles = {m["title"] for m in members}
        if len(titles) > 1:
            findings.append(finding(
                "R8", "P1", "Casing conflict inside group %r" % n,
                "; ".join("%s (%s)" % (m["title"], m["collection_id"]) for m in members),
                "Pick one canonical casing",
                "rename"))

    # R2 — fragmented collections
    for c in sorted(governable, key=lambda x: x.get("bookmarks_count") or 0):
        if 0 < (c.get("bookmarks_count") or 0) <= FRAGMENT_THRESHOLD:
            findings.append(finding(
                "R2", "P2", "Fragmented collection: %d bookmarks" % c["bookmarks_count"],
                "%s (%s, in %s)" % (c["title"], c["collection_id"], parent_chain(c, by_id) or "top level"),
                "Merge candidate — confirm theme overlap first",
                "merge"))
        elif c.get("bookmarks_count") == 0:
            has_children = any(x.get("parent_id") == c["collection_id"] for x in governable)
            if not has_children:
                # R3 — empty (no children either)
                findings.append(finding(
                    "R3", "P1", "Empty collection",
                    "%s (%s, in %s)" % (c["title"], c["collection_id"], parent_chain(c, by_id) or "top level"),
                    "Repurpose or remove in the app; this skill never deletes",
                    "none"))

    # R4 — hollow top-level containers
    top = [c for c in governable if c.get("parent_id") is None]
    for c in sorted(top, key=lambda x: x.get("bookmarks_count") or 0):
        direct = c.get("bookmarks_count") or 0
        total = c.get("total_bookmarks_count") or 0
        if direct <= HOLLOW_TOP_DIRECT and total > direct:
            findings.append(finding(
                "R4", "P2", "Hollow container: %d direct / %d total (children carry content)" % (direct, total),
                "%s (%s)" % (c["title"], c["collection_id"]),
                "Acceptable as a pure container — informational only",
                "none"))

    # R5 — Unsorted backlog
    n_unsorted = len(unsorted_items)
    if n_unsorted:
        priority = "P0" if n_unsorted > UNSORTED_P0 else "P1"
        rows = []
        for b in unsorted_items[:30]:
            title = b.get("title") or b.get("url") or "?"
            domain = b.get("domain") or b.get("link") or ""
            rows.append("- %s (%s)" % (title, domain))
        if n_unsorted > 30:
            rows.append("- ... and %d more" % (n_unsorted - 30))
        findings.append(finding(
            "R5", priority, "Unsorted backlog: %d bookmarks" % n_unsorted,
            "\n".join(rows),
            "Batch-assign to collections; run raindrop-bookmark-organizer first if metadata is missing",
            "move-bookmarks"))

    # R6 — singular/plural pairs
    sing = {}
    for c in governable:
        sing.setdefault(singular_form(c["title"]), set()).add(c["title"])
    for base, variants in sorted(sing.items()):
        if len(variants) > 1:
            members = [c for c in governable if c["title"] in variants]
            findings.append(finding(
                "R6", "P1", "Singular/plural pair: %s" % " vs ".join(sorted(variants)),
                "; ".join("%s (%s)" % (m["title"], m["collection_id"]) for m in members),
                "Pick one canonical form, then treat as duplicates",
                "merge-or-rename"))

    # R7 — language mix
    ascii_titles = [c for c in governable if not CJK_RE.search(c["title"] or "")]
    cjk_titles = [c for c in governable if CJK_RE.search(c["title"] or "")]
    if governable and len(ascii_titles) / len(governable) >= 0.8 and cjk_titles:
        for c in cjk_titles:
            findings.append(finding(
                "R7", "P2", "Language mix: CJK title in an ASCII-dominant library",
                "%s (%s)" % (c["title"], c["collection_id"]),
                "Align with the dominant language convention",
                "rename"))

    # R9 — orphaned hierarchy
    for c in governable:
        pid = c.get("parent_id")
        if pid is not None and pid not in by_id:
            findings.append(finding(
                "R9", "P1", "Parent id %s does not exist" % pid,
                "%s (%s)" % (c["title"], c["collection_id"]),
                "Re-parent to an existing collection",
                "re-parent"))

    # R10 — over-deep hierarchy
    for c in governable:
        if depth_of(c, by_id) > MAX_DEPTH_OK:
            findings.append(finding(
                "R10", "P2", "Hierarchy deeper than %d levels" % MAX_DEPTH_OK,
                "%s (%s, in %s)" % (c["title"], c["collection_id"], parent_chain(c, by_id)),
                "Flatten one level",
                "re-parent"))

    return governable, findings


ORDER = {"P0": 0, "P1": 1, "P2": 2}


def render(collections, unsorted_items, stats, findings):
    lines = []
    lines.append("# Raindrop Collection Audit Report")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    total_bookmarks = sum(c.get("bookmarks_count") or 0 for c in collections)
    top_level = [c for c in collections if c.get("collection_id") not in (UNSORTED_ID, TRASH_ID)
                 and c.get("parent_id") is None]
    by_id = {c.get("collection_id"): c for c in collections if c.get("collection_id") is not None}
    governable = [c for c in collections
                  if c.get("collection_id") not in (UNSORTED_ID, TRASH_ID)]
    max_depth = max((depth_of(c, by_id) for c in governable), default=0)
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append("| Collections (excl. Unsorted/Trash) | %d |" % len(governable))
    lines.append("| Top-level collections | %d |" % len(top_level))
    lines.append("| Max hierarchy depth | %d |" % max_depth)
    lines.append("| Bookmarks (sum of direct counts) | %d |" % total_bookmarks)
    lines.append("| Unsorted backlog | %d |" % len(unsorted_items))
    if stats:
        b = stats.get("bookmarks") or {}
        lines.append("| Library total (per account stats) | %s |" % b.get("total", "?"))
        lines.append("| Tags | %s |" % stats.get("tags", "?"))
        lines.append("| Highlights | %s |" % stats.get("highlights", "?"))
    lines.append("")

    for prio in ("P0", "P1", "P2"):
        rows = sorted([f for f in findings if f["priority"] == prio],
                      key=lambda f: f["rule"])
        lines.append("## %s findings (%d)" % (prio, len(rows)))
        lines.append("")
        if not rows:
            lines.append("None.")
            lines.append("")
            continue
        lines.append("| Rule | Finding | Evidence | Suggestion | Operation |")
        lines.append("|---|---|---|---|---|")
        for f in rows:
            evidence = f["evidence"].replace("\n", " <br> ").replace("|", "\\|")
            lines.append("| %s | %s | %s | %s | %s |" % (
                f["rule"], f["problem"], evidence, f["suggestion"], f["operation"]))
        lines.append("")

    ops = {}
    for f in findings:
        ops[f["operation"]] = ops.get(f["operation"], 0) + 1
    lines.append("## Operation summary")
    lines.append("")
    lines.append("| Operation | Findings |")
    lines.append("|---|---|")
    for op, n in sorted(ops.items()):
        lines.append("| %s | %d |" % (op, n))
    lines.append("")
    lines.append("Next step: pick items for the Phase 2 execution plan. "
                 "No writes happen without an explicitly confirmed plan.")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Render a Raindrop collection audit report.")
    ap.add_argument("--collections", required=True, help="collections JSON dump")
    ap.add_argument("--unsorted", help="Unsorted backlog JSON dump (optional)")
    ap.add_argument("--user", help="fetch_current_user JSON dump (optional)")
    ap.add_argument("--out", help="output Markdown path (default: stdout)")
    args = ap.parse_args()

    collections = load_records(args.collections, "collections")
    unsorted_items = load_records(args.unsorted, "bookmarks") if args.unsorted else []
    stats = None
    if args.user:
        rec = load_records(args.user, "user")
        if rec and isinstance(rec[0], dict):
            stats = (rec[0].get("user") or {}).get("statistics")

    governable, findings = audit(collections, unsorted_items)
    report = render(collections, unsorted_items, stats, findings)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print("report written to %s (%d findings, %d collections scanned)"
              % (args.out, len(findings), len(governable)))
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
