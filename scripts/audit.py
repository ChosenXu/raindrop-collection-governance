#!/usr/bin/env python3
"""Deterministic audit report renderer for Raindrop collection governance.

Reads JSON dumps collected via the Raindrop MCP server (read-only) and renders
a Markdown audit report classified per references/audit-rules.md (R1-R10).

Usage:
    python3 audit.py --collections collections.json \
                     [--unsorted unsorted.json] \
                     [--user user.json] \
                     [--lang auto|zh|en] [--sample "user's request text"] \
                     [--out report.md]

Language: the caller (agent workflow) detects the user's invocation language
and passes it via --lang. With --lang auto (default) the report language is
detected from --sample by CJK-character ratio; without a sample it falls back
to English. A rendered report is strictly monolingual — proper nouns, titles
and URLs stay verbatim.

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
FLAT_HEAVY_THRESHOLD = 40       # FR1: direct >= 40 with no children -> split candidate
DOMINANCE_RATIO = 0.4           # FR2: one top-level holding > 40% of the library
TINY_TOP_THRESHOLD = 8          # FR3: top-level total <= 8 -> review placement
CJK_RATIO_ZH = 0.15             # --lang auto: sample is Chinese above this CJK ratio

# ---------------------------------------------------------------- language

def detect_language(sample):
    """CJK ratio of the sample above CJK_RATIO_ZH -> zh, else en (fallback)."""
    if not sample:
        return "en"
    cjk = len(CJK_RE.findall(sample))
    letters = len(re.findall(r"[A-Za-z]", sample))
    total = cjk + letters
    if total == 0:
        return "en"
    return "zh" if cjk / total > CJK_RATIO_ZH else "en"


def t(zh, en):
    """Bilingual string literal: a (zh, en) tuple."""
    return (zh, en)


STR = {
    "report_title": t("Raindrop 收藏夹盘点报告", "Raindrop Collection Audit Report"),
    "overview": t("总览", "Overview"),
    "metric": t("指标", "Metric"),
    "value": t("数值", "Value"),
    "collections_total": t("收藏夹数（不含未分类/回收站）", "Collections (excl. Unsorted/Trash)"),
    "top_level": t("顶层收藏夹", "Top-level collections"),
    "max_depth": t("最大层级深度", "Max hierarchy depth"),
    "bookmarks_sum": t("书签总数（直属计数求和）", "Bookmarks (sum of direct counts)"),
    "unsorted_backlog": t("未分类积压", "Unsorted backlog"),
    "library_total": t("账号统计总数", "Library total (per account stats)"),
    "tags": t("标签数", "Tags"),
    "highlights": t("划线数", "Highlights"),
    "findings_header": t("发现（{n} 条）", "findings ({n})"),
    "none": t("无。", "None."),
    "col_rule": t("规则", "Rule"),
    "col_finding": t("发现", "Finding"),
    "col_evidence": t("证据", "Evidence"),
    "col_suggestion": t("建议", "Suggestion"),
    "col_operation": t("操作", "Operation"),
    "op_summary": t("操作汇总", "Operation summary"),
    "col_operation2": t("操作", "Operation"),
    "col_findings_n": t("发现数", "Findings"),
    "footer": t("下一步：从发现中勾选条目，生成第二阶段执行计划。"
                "未经你明确确认的计划不会触发任何写入。",
                "Next step: pick items for the Phase 2 execution plan. "
                "No writes happen without an explicitly confirmed plan."),

    # operations (display labels)
    "op_merge": t("合并", "merge"),
    "op_merge_or_rename": t("合并或改名", "merge-or-rename"),
    "op_rename": t("改名", "rename"),
    "op_reparent": t("调整层级", "re-parent"),
    "op_move": t("移动书签", "move-bookmarks"),
    "op_none": t("无需操作", "none"),

    # rule texts
    "r1_same_parent": t("同一父级下收藏夹重名：{title!r} ×{n}",
                        "Duplicate title under the same parent: {title!r} x{n}"),
    "r1_cross_parent": t("不同父级下同名收藏夹：{title!r} ×{n}",
                         "Same title across different parents: {title!r} x{n}"),
    "r1_suggestion": t("改其中一个的名字，或将较小者合并入较大者",
                       "Rename one, or merge the smaller into the larger"),
    "r2_problem": t("碎片收藏夹：仅 {n} 条书签", "Fragmented collection: {n} bookmarks"),
    "r2_suggestion": t("合并候选——先确认主题是否重叠", "Merge candidate — confirm theme overlap first"),
    "r3_problem": t("空收藏夹", "Empty collection"),
    "r3_suggestion": t("在应用内改造或移除；本技能从不删除", "Repurpose or remove in the app; this skill never deletes"),
    "r4_problem": t("空心容器：直属 {d} 条 / 总计 {t} 条（内容在子级）",
                    "Hollow container: {d} direct / {t} total (children carry content)"),
    "r4_suggestion": t("作为纯容器可以接受——仅提示", "Acceptable as a pure container — informational only"),
    "r5_problem": t("未分类积压：{n} 条书签", "Unsorted backlog: {n} bookmarks"),
    "r5_suggestion": t("批量归位到收藏夹；若元数据缺失可先跑 raindrop-bookmark-organizer",
                       "Batch-assign to collections; run raindrop-bookmark-organizer first if metadata is missing"),
    "r5_more": t("……另有 {n} 条", "... and {n} more"),
    "r6_problem": t("单复数混用：{variants}", "Singular/plural pair: {variants}"),
    "r6_suggestion": t("选定一种规范形式，然后按重名处理", "Pick one canonical form, then treat as duplicates"),
    "r7_problem": t("语言混用：以英文为主体的库中出现中文标题", "Language mix: CJK title in an ASCII-dominant library"),
    "r7_suggestion": t("与主体语言的命名惯例保持一致", "Align with the dominant language convention"),
    "r8_problem": t("大小写冲突（组 {group!r}）", "Casing conflict inside group {group!r}"),
    "r8_suggestion": t("选定一种规范大小写", "Pick one canonical casing"),
    "r9_problem": t("父级 id {pid} 不存在", "Parent id {pid} does not exist"),
    "r9_suggestion": t("重新挂到已存在的收藏夹下", "Re-parent to an existing collection"),
    "r10_problem": t("层级超过 {d} 层", "Hierarchy deeper than {d} levels"),
    "r10_suggestion": t("压平一层", "Flatten one level"),
    "top_level_txt": t("顶层", "top level"),
    "in_txt": t("位于", "in"),

    # framework review mode
    "fw_report_title": t("Raindrop 收藏夹框架评审报告", "Raindrop Collection Framework Review"),
    "fw_structure": t("顶层结构分布", "Top-level structure"),
    "fw_col_tree": t("顶层树", "Top-level tree"),
    "fw_col_direct": t("直属书签", "Direct"),
    "fw_col_total": t("总计", "Total"),
    "fw_col_children": t("子夹数", "Children"),
    "fw_col_depth": t("最大深度", "Max depth"),
    "fw_col_share": t("占库比", "Share"),
    "fw_warnings": t("确定性预警", "Deterministic warnings"),
    "fw_flat_heavy": t("平铺大夹：{title} 直属 {n} 条且无子夹，建议按主题拆分 2-3 个子夹",
                       "Flat-heavy top-level: {title} holds {n} direct bookmarks with no children — consider splitting into 2-3 sub-collections"),
    "fw_dominance": t("体量失衡：{title} 占全库 {pct}%，是超级领域树；留意其他顶层的发展空间",
                      "Size dominance: {title} holds {pct}% of the library — a super-tree; watch growth elsewhere"),
    "fw_tiny_top": t("微型顶层：{title} 仅 {n} 条，检查是否能并入相邻领域的树",
                     "Tiny top-level: {title} has only {n} bookmarks — check whether it belongs under an adjacent domain tree"),
    "fw_semantic_note": t("语义层（由 AI 结合夹内内容判断，非本脚本产出）：分类轴混用分析、语义重叠夹对、"
                          "错位书签线索与扩展性建议，流程见 SKILL.md 的框架评审节。",
                          "Semantic layer (judged by the agent from collection contents, not this script): taxonomy-axis "
                          "mixing, overlapping collection pairs, misfiled bookmarks and extensibility advice — see the "
                          "framework-review section in SKILL.md."),
    "fw_none": t("无。", "None."),
}

OPERATION_LABELS = {
    "merge": "op_merge",
    "merge-or-rename": "op_merge_or_rename",
    "rename": "op_rename",
    "re-parent": "op_reparent",
    "move-bookmarks": "op_move",
    "none": "op_none",
}


def L(key, lang, **kw):
    """Localized string with optional {kw} interpolation."""
    idx = 0 if lang == "zh" else 1
    s = STR[key][idx]
    if kw:
        return s.format(**kw)
    return s


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


def parent_chain(col, by_id, lang):
    chain = []
    cur = col
    seen = set()
    while cur is not None and cur["collection_id"] not in seen:
        seen.add(cur["collection_id"])
        chain.append(cur["title"])
        pid = cur.get("parent_id")
        cur = by_id.get(pid) if pid is not None else None
    if not chain:
        return L("top_level_txt", lang)
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
    """problem and suggestion are (zh, en) tuples; evidence is language-neutral data."""
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
    for c in governable:
        groups.setdefault(norm_title(c["title"]), []).append(c)
    for n, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        parents = {m.get("parent_id") for m in members}
        chain_txt = "; ".join("%s (%s, %s %s)" % (m["title"], m["collection_id"],
                                                  L("in_txt", "zh"), parent_chain(m, by_id, "zh"))
                              for m in members)
        chain_txt_en = "; ".join("%s (%s, in %s)" % (m["title"], m["collection_id"],
                                                    parent_chain(m, by_id, "en"))
                                 for m in members)
        evidence = (chain_txt, chain_txt_en)
        if len(parents) == 1 and None not in parents:
            findings.append(finding(
                "R1", "P0",
                (L("r1_same_parent", "zh", title=members[0]["title"], n=len(members)),
                 L("r1_same_parent", "en", title=members[0]["title"], n=len(members))),
                evidence,
                STR["r1_suggestion"],
                "merge-or-rename"))
        else:
            findings.append(finding(
                "R1", "P1",
                (L("r1_cross_parent", "zh", title=members[0]["title"], n=len(members)),
                 L("r1_cross_parent", "en", title=members[0]["title"], n=len(members))),
                evidence,
                STR["r1_suggestion"],
                "merge-or-rename"))
        # R8 — exact-case duplicates inside the group
        titles = {m["title"] for m in members}
        if len(titles) > 1:
            findings.append(finding(
                "R8", "P1",
                (L("r8_problem", "zh", group=n), L("r8_problem", "en", group=n)),
                ("; ".join("%s (%s)" % (m["title"], m["collection_id"]) for m in members),) * 2,
                STR["r8_suggestion"],
                "rename"))

    # R2 / R3 — fragmented and empty collections
    for c in sorted(governable, key=lambda x: x.get("bookmarks_count") or 0):
        count = c.get("bookmarks_count") or 0
        ev = lambda lang: "%s (%s, %s %s)" % (c["title"], c["collection_id"],
                                              L("in_txt", lang), parent_chain(c, by_id, lang))
        if 0 < count <= FRAGMENT_THRESHOLD:
            findings.append(finding(
                "R2", "P2",
                (L("r2_problem", "zh", n=count), L("r2_problem", "en", n=count)),
                (ev("zh"), ev("en")),
                STR["r2_suggestion"],
                "merge"))
        elif count == 0:
            has_children = any(x.get("parent_id") == c["collection_id"] for x in governable)
            if not has_children:
                # R3 — empty (no children either)
                findings.append(finding(
                    "R3", "P1",
                    (L("r3_problem", "zh"), L("r3_problem", "en")),
                    (ev("zh"), ev("en")),
                    STR["r3_suggestion"],
                    "none"))

    # R4 — hollow top-level containers
    top = [c for c in governable if c.get("parent_id") is None]
    for c in sorted(top, key=lambda x: x.get("bookmarks_count") or 0):
        direct = c.get("bookmarks_count") or 0
        total = c.get("total_bookmarks_count") or 0
        if direct <= HOLLOW_TOP_DIRECT and total > direct:
            findings.append(finding(
                "R4", "P2",
                (L("r4_problem", "zh", d=direct, t=total),
                 L("r4_problem", "en", d=direct, t=total)),
                ("%s (%s)" % (c["title"], c["collection_id"]),) * 2,
                STR["r4_suggestion"],
                "none"))

    # R5 — Unsorted backlog
    n_unsorted = len(unsorted_items)
    if n_unsorted:
        priority = "P0" if n_unsorted > UNSORTED_P0 else "P1"

        def unsorted_evidence(lang):
            rows = []
            for b in unsorted_items[:30]:
                title = b.get("title") or b.get("url") or "?"
                domain = b.get("domain") or b.get("link") or ""
                rows.append("- %s (%s)" % (title, domain))
            if n_unsorted > 30:
                rows.append("- %s" % L("r5_more", lang, n=n_unsorted - 30))
            return " <br> ".join(rows)

        findings.append(finding(
            "R5", priority,
            (L("r5_problem", "zh", n=n_unsorted), L("r5_problem", "en", n=n_unsorted)),
            (unsorted_evidence("zh"), unsorted_evidence("en")),
            STR["r5_suggestion"],
            "move-bookmarks"))

    # R6 — singular/plural pairs
    sing = {}
    for c in governable:
        sing.setdefault(singular_form(c["title"]), set()).add(c["title"])
    for base, variants in sorted(sing.items()):
        if len(variants) > 1:
            members = [c for c in governable if c["title"] in variants]
            variants_txt = " vs ".join(sorted(variants))
            findings.append(finding(
                "R6", "P1",
                (L("r6_problem", "zh", variants=variants_txt),
                 L("r6_problem", "en", variants=variants_txt)),
                ("; ".join("%s (%s)" % (m["title"], m["collection_id"]) for m in members),) * 2,
                STR["r6_suggestion"],
                "merge-or-rename"))

    # R7 — language mix
    ascii_titles = [c for c in governable if not CJK_RE.search(c["title"] or "")]
    cjk_titles = [c for c in governable if CJK_RE.search(c["title"] or "")]
    if governable and len(ascii_titles) / len(governable) >= 0.8 and cjk_titles:
        for c in cjk_titles:
            findings.append(finding(
                "R7", "P2",
                (L("r7_problem", "zh"), L("r7_problem", "en")),
                ("%s (%s)" % (c["title"], c["collection_id"]),) * 2,
                STR["r7_suggestion"],
                "rename"))

    # R9 — orphaned hierarchy
    for c in governable:
        pid = c.get("parent_id")
        if pid is not None and pid not in by_id:
            findings.append(finding(
                "R9", "P1",
                (L("r9_problem", "zh", pid=pid), L("r9_problem", "en", pid=pid)),
                ("%s (%s)" % (c["title"], c["collection_id"]),) * 2,
                STR["r9_suggestion"],
                "re-parent"))

    # R10 — over-deep hierarchy
    for c in governable:
        if depth_of(c, by_id) > MAX_DEPTH_OK:
            findings.append(finding(
                "R10", "P2",
                (L("r10_problem", "zh", d=MAX_DEPTH_OK), L("r10_problem", "en", d=MAX_DEPTH_OK)),
                ("%s (%s, %s %s)" % (c["title"], c["collection_id"],
                                     L("in_txt", "zh"), parent_chain(c, by_id, "zh")),
                 "%s (%s, in %s)" % (c["title"], c["collection_id"], parent_chain(c, by_id, "en"))),
                STR["r10_suggestion"],
                "re-parent"))

    return governable, findings


ORDER = {"P0": 0, "P1": 1, "P2": 2}


def render(collections, unsorted_items, stats, findings, lang):
    idx = 0 if lang == "zh" else 1
    lines = []
    lines.append("# %s" % STR["report_title"][idx])
    lines.append("")
    lines.append("## %s" % STR["overview"][idx])
    lines.append("")
    total_bookmarks = sum(c.get("bookmarks_count") or 0 for c in collections)
    top_level = [c for c in collections if c.get("collection_id") not in (UNSORTED_ID, TRASH_ID)
                 and c.get("parent_id") is None]
    by_id = {c.get("collection_id"): c for c in collections if c.get("collection_id") is not None}
    governable = [c for c in collections
                  if c.get("collection_id") not in (UNSORTED_ID, TRASH_ID)]
    max_depth = max((depth_of(c, by_id) for c in governable), default=0)
    lines.append("| %s | %s |" % (STR["metric"][idx], STR["value"][idx]))
    lines.append("|---|---|")
    lines.append("| %s | %d |" % (STR["collections_total"][idx], len(governable)))
    lines.append("| %s | %d |" % (STR["top_level"][idx], len(top_level)))
    lines.append("| %s | %d |" % (STR["max_depth"][idx], max_depth))
    lines.append("| %s | %d |" % (STR["bookmarks_sum"][idx], total_bookmarks))
    lines.append("| %s | %d |" % (STR["unsorted_backlog"][idx], len(unsorted_items)))
    if stats:
        b = stats.get("bookmarks") or {}
        lines.append("| %s | %s |" % (STR["library_total"][idx], b.get("total", "?")))
        lines.append("| %s | %s |" % (STR["tags"][idx], stats.get("tags", "?")))
        lines.append("| %s | %s |" % (STR["highlights"][idx], stats.get("highlights", "?")))
    lines.append("")

    for prio in ("P0", "P1", "P2"):
        rows = sorted([f for f in findings if f["priority"] == prio],
                      key=lambda f: f["rule"])
        lines.append("## %s %s" % (prio, STR["findings_header"][idx].format(n=len(rows))))
        lines.append("")
        if not rows:
            lines.append(STR["none"][idx])
            lines.append("")
            continue
        lines.append("| %s | %s | %s | %s | %s |" % (
            STR["col_rule"][idx], STR["col_finding"][idx], STR["col_evidence"][idx],
            STR["col_suggestion"][idx], STR["col_operation"][idx]))
        lines.append("|---|---|---|---|---|")
        for f in rows:
            evidence = f["evidence"][idx].replace("\n", " <br> ").replace("|", "\\|")
            op_label = STR[OPERATION_LABELS[f["operation"]]][idx]
            lines.append("| %s | %s | %s | %s | %s |" % (
                f["rule"], f["problem"][idx], evidence, f["suggestion"][idx], op_label))
        lines.append("")

    ops = {}
    for f in findings:
        ops[f["operation"]] = ops.get(f["operation"], 0) + 1
    lines.append("## %s" % STR["op_summary"][idx])
    lines.append("")
    lines.append("| %s | %s |" % (STR["col_operation2"][idx], STR["col_findings_n"][idx]))
    lines.append("|---|---|")
    for op, n in sorted(ops.items()):
        lines.append("| %s | %d |" % (STR[OPERATION_LABELS[op]][idx], n))
    lines.append("")
    lines.append(STR["footer"][idx])
    lines.append("")
    return "\n".join(lines)


def framework(collections):
    """Deterministic framework metrics per FR1-FR3 (semantic FR4-FR5 are agent-layer)."""
    by_id = {c.get("collection_id"): c for c in collections if c.get("collection_id") is not None}
    governable = [c for c in collections
                  if c.get("collection_id") not in (UNSORTED_ID, TRASH_ID)]
    tops = [c for c in governable if c.get("parent_id") is None]
    rows = []
    for tcol in tops:
        children = [c for c in governable if c.get("parent_id") == tcol["collection_id"]]
        total = tcol.get("total_bookmarks_count") or tcol.get("bookmarks_count") or 0
        max_depth = 1
        for ch in children:
            max_depth = max(max_depth, depth_of(ch, by_id))
        rows.append({
            "title": tcol["title"],
            "collection_id": tcol["collection_id"],
            "direct": tcol.get("bookmarks_count") or 0,
            "total": total,
            "children": len(children),
            "max_depth": max_depth,
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    lib_total = sum(r["total"] for r in rows) or 1
    warnings = []
    for r in rows:
        if r["children"] == 0 and r["total"] >= FLAT_HEAVY_THRESHOLD:
            warnings.append(("FR1", L("fw_flat_heavy", "zh", title=r["title"], n=r["total"]),
                             L("fw_flat_heavy", "en", title=r["title"], n=r["total"])))
        if r["total"] / lib_total > DOMINANCE_RATIO:
            warnings.append(("FR2", L("fw_dominance", "zh", title=r["title"],
                                      pct=round(r["total"] / lib_total * 100)),
                             L("fw_dominance", "en", title=r["title"],
                               pct=round(r["total"] / lib_total * 100))))
        if r["total"] <= TINY_TOP_THRESHOLD:
            warnings.append(("FR3", L("fw_tiny_top", "zh", title=r["title"], n=r["total"]),
                             L("fw_tiny_top", "en", title=r["title"], n=r["total"])))
    return rows, lib_total, warnings


def render_framework(collections, lang):
    idx = 0 if lang == "zh" else 1
    rows, lib_total, warnings = framework(collections)
    lines = []
    lines.append("# %s" % STR["fw_report_title"][idx])
    lines.append("")
    lines.append("## %s" % STR["fw_structure"][idx])
    lines.append("")
    lines.append("| %s | %s | %s | %s | %s | %s |" % (
        STR["fw_col_tree"][idx], STR["fw_col_direct"][idx], STR["fw_col_total"][idx],
        STR["fw_col_children"][idx], STR["fw_col_depth"][idx], STR["fw_col_share"][idx]))
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append("| %s | %d | %d | %d | %d | %d%% |" % (
            r["title"], r["direct"], r["total"], r["children"],
            r["max_depth"], round(r["total"] / lib_total * 100)))
    lines.append("")
    lines.append("## %s" % STR["fw_warnings"][idx])
    lines.append("")
    if not warnings:
        lines.append(STR["fw_none"][idx])
    else:
        lines.append("| %s | %s |" % (STR["col_rule"][idx], STR["col_finding"][idx]))
        lines.append("|---|---|")
        for rule, zh, en in warnings:
            lines.append("| %s | %s |" % (rule, (zh, en)[idx]))
    lines.append("")
    lines.append(STR["fw_semantic_note"][idx])
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Render a Raindrop collection audit report.")
    ap.add_argument("--collections", required=True, help="collections JSON dump")
    ap.add_argument("--unsorted", help="Unsorted backlog JSON dump (optional)")
    ap.add_argument("--user", help="fetch_current_user JSON dump (optional)")
    ap.add_argument("--lang", choices=("auto", "zh", "en"), default="auto",
                    help="report language: zh / en, or auto (detect from --sample, fallback en)")
    ap.add_argument("--sample", help="the user's request text, used by --lang auto detection")
    ap.add_argument("--mode", choices=("audit", "framework"), default="audit",
                    help="audit = collection-level findings (R1-R10); framework = top-level structure review (FR1-FR3)")
    ap.add_argument("--out", help="output Markdown path (default: stdout)")
    args = ap.parse_args()

    lang = detect_language(args.sample) if args.lang == "auto" else args.lang

    collections = load_records(args.collections, "collections")
    unsorted_items = load_records(args.unsorted, "bookmarks") if args.unsorted else []
    stats = None
    if args.user:
        rec = load_records(args.user, "user")
        if rec and isinstance(rec[0], dict):
            stats = (rec[0].get("user") or {}).get("statistics")

    if args.mode == "framework":
        report = render_framework(collections, lang)
        n_out = 0
    else:
        governable, findings = audit(collections, unsorted_items)
        report = render(collections, unsorted_items, stats, findings, lang)
        n_out = len(findings)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print("report [%s/%s] written to %s (%s, %d collections scanned)"
              % (lang, args.mode, args.out,
                 "%d findings" % n_out if args.mode == "audit" else "framework metrics",
                 len(collections)))
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
