#!/usr/bin/env python3
"""Optional Jev pre-screener for relocation candidates (read-only, no Raindrop writes).

Blind-classifies every bookmark against the REAL collection tree (derived from a
`find_collections` dump) using the TypeSafe Jev System One model, then compares the
predicted location with the bookmark's current location in code. Design rules learned
in calibration (2026-09-21):

  1. Blind classification: the state contains ONLY the bookmark (title / tags / domain).
     Never include the current collection's self-description — it leaks the answer.
  2. Hierarchical routing: Choice over top-level trees, then descend into subcategories
     (up to depth 3, with a "stay" option at each level).
  3. Confidence bands replace subjective wording: >= high -> candidate list,
     medium -> review list, below medium -> discarded.

Inputs are the JSON dumps the audit phase already saves under /tmp/. The script never
writes to Raindrop and never touches bookmark metadata.

Cost model: up to 3 Jev calls per bookmark (~600-1200 tokens each). A full 1000+
bookmark library is a five-figure-token run — use --limit for a taste first.
Each HTTP call is capped at 30 s and the SDK retries 429/5xx automatically
(3 attempts), so a stuck request can never hang the run indefinitely.

Requires Python >= 3.10 and `pip install "typesafe-sdk>=0.7.0,<0.8"` (verified
against 0.7.0 — the pin matters because timeout/retry behavior is versioned);
`TYPESAFE_API_KEY` in the environment. This script is OPTIONAL: without it (or
without the key) the skill falls back to its built-in tag/domain/title heuristic.

Output: JSON with per-bookmark predictions, confidence bands and a summary, written
next to the input dumps (default) or to --out.
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

try:
    from typesafe_sdk import Choice, Noul, TypeSafeClient
    SDK_AVAILABLE = True
    SDK_IMPORT_ERROR = None
except Exception as _sdk_exc:  # ImportError or a broken installation
    SDK_AVAILABLE = False
    SDK_IMPORT_ERROR = str(_sdk_exc)

OPT_OUT_ENV = "RAINDROP_GOV_JEV"
PY_MIN = (3, 10)

HIGH_DEFAULT = 0.85
MEDIUM_DEFAULT = 0.50
UNSORTED_ID = -1
TRASH_ID = -99
MAX_DEPTH = 3  # top-level = 1; descend at most to depth 3
REQUEST_TIMEOUT = 30.0  # seconds per HTTP operation (SDK default 10 s is tight for large criteria sets)
FUTURE_TIMEOUT = 300  # seconds per bookmark across all its calls incl. SDK retries


def load_dump(path, key):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in (key, "items", "data"):
            if isinstance(data.get(k), list):
                return data[k]
    raise SystemExit("error: %s does not contain a '%s' list" % (path, key))


def build_tree(collections):
    by_id = {}
    for c in collections:
        cid = c.get("collection_id")
        if cid is not None:
            by_id[cid] = c
    govable = [c for c in collections
               if c.get("collection_id") not in (UNSORTED_ID, TRASH_ID)]
    tops = [c for c in govable if c.get("parent_id") is None]
    children = {}
    for c in govable:
        pid = c.get("parent_id")
        if pid is not None and pid in by_id:
            children.setdefault(pid, []).append(c)
    return by_id, govable, tops, children


def node_desc(node, children):
    d = node["title"]
    kids = children.get(node.get("collection_id"), [])
    if kids:
        d += " — subcategories: " + ", ".join(k["title"] for k in kids)
    return d


def python_ok():
    ok = sys.version_info >= PY_MIN
    return ok, "%d.%d.%d" % sys.version_info[:3]


_tls = threading.local()


def get_client():
    """One TypeSafeClient per thread: the SDK does not document thread safety,
    so worker threads never share a client instance. Every call carries an
    explicit timeout; 429/5xx retries are built into the SDK (3 attempts)."""
    client = getattr(_tls, "client", None)
    if client is None:
        client = TypeSafeClient(timeout=REQUEST_TIMEOUT)
        _tls.client = client
    return client


def probe(do_auth_call=False):
    """Environment verdict. Local-only by default; do_auth_call adds one tiny
    request to verify the key. Never raises — every failure becomes a status."""
    py_ok, py_ver = python_ok()
    verdict = {
        "opt_out": os.environ.get(OPT_OUT_ENV, "").strip().lower() in ("off", "0", "false", "no"),
        "api_key": bool(os.environ.get("TYPESAFE_API_KEY")),
        "sdk_available": SDK_AVAILABLE,
        "sdk_error": SDK_IMPORT_ERROR,
        "python_ok": py_ok,
        "python_version": py_ver,
        "auth": "not_tested",
        "ready": False,
    }
    if verdict["opt_out"]:
        verdict["auth"] = "skipped (opt-out)"
        return verdict
    if not (verdict["api_key"] and SDK_AVAILABLE and py_ok):
        return verdict
    if not do_auth_call:
        verdict["ready"] = True  # local checks passed; auth untested
        return verdict
    try:
        client = get_client()
        r = client.system_one(
            state="ping",
            questions={"p": Noul(instructions="Is this a ping?")},
        )
        n = getattr(r.answers["p"], "noul", -1)
        verdict["auth"] = "ok" if 0 <= n <= 1 else "unexpected_response"
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        verdict["auth"] = "auth_failed" if ("401" in msg or "403" in msg) else "unreachable"
    verdict["ready"] = verdict["auth"] == "ok"
    return verdict


def classify_flat(client, bm, categories):
    """Validated strategy: blind Choice over well-described categories (NOT the raw
    tree), then code maps the category to its collection(s). A bookmark is a
    relocation candidate only when its current collection is NOT among the
    predicted category's mapped collections."""
    state = {"bookmark": {
        "title": bm.get("title") or "",
        "tags": bm.get("tags") or [],
        "domain": bm.get("domain") or "",
    }}
    criteria = {name: spec["description"] for name, spec in categories.items()}
    r = client.system_one(
        state=state,
        questions={"category": Choice(
            instructions=("Classify this bookmark into exactly one category by its "
                          "PRIMARY purpose, judging from title, tags and domain."),
            criteria=criteria,
        )},
    )
    a = r.answers["category"]
    mapped = categories[a.choice].get("collections") or []
    return {"category": a.choice, "mapped": mapped, "confidence": a.confidence, "calls": 1}


def classify(client, bm, tops, children):
    """Two-stage (up to depth-3) blind classification. Returns prediction dict."""
    state = {"bookmark": {
        "title": bm.get("title") or "",
        "tags": bm.get("tags") or [],
        "domain": bm.get("domain") or "",
    }}
    calls = 0

    s1_options = {str(t["collection_id"]): node_desc(t, children) for t in tops}
    r1 = client.system_one(
        state=state,
        questions={"tree": Choice(
            instructions=("Which top-level area of a bookmark library does this bookmark "
                          "belong to, by its PRIMARY purpose? Pick exactly one."),
            criteria=s1_options,
        )},
    )
    calls += 1
    tree_id = int(r1.answers["tree"].choice)
    tree_conf = r1.answers["tree"].confidence
    node_id, node_conf = tree_id, tree_conf

    for _ in range(MAX_DEPTH - 1):
        kids = children.get(node_id, [])
        if not kids:
            break
        node = by_id_local[node_id]
        options = {"stay": "%s (keep it at this level)" % node["title"]}
        for k in kids:
            options[str(k["collection_id"])] = node_desc(k, children)
        r2 = client.system_one(
            state=state,
            questions={"sub": Choice(
                instructions=("Inside '%s', which subcategory fits this bookmark best, "
                              "or should it stay at this level?" % node["title"]),
                criteria=options,
            )},
        )
        calls += 1
        sub = r2.answers["sub"]
        if sub.choice == "stay":
            node_conf = sub.confidence
            break
        node_id = int(sub.choice)
        node_conf = sub.confidence

    return {
        "predicted": node_id,
        "stage1_tree": tree_id,
        "stage1_confidence": tree_conf,
        "confidence": node_conf,
        "calls": calls,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Optional Jev pre-screener: blind-classify bookmarks against the "
                    "collection tree and output relocation candidates (read-only).")
    ap.add_argument("--collections", required=False, help="find_collections JSON dump")
    ap.add_argument("--bookmarks", required=False,
                    help="bookmarks JSON dump: [{bookmark_id, title, tags, domain?, collection_id}, ...]")
    ap.add_argument("--out", help="output JSON path (default: jev-precheck-results.json next to --bookmarks)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, help="process only the first N bookmarks (cost guard)")
    ap.add_argument("--high", type=float, default=HIGH_DEFAULT, help="high-confidence threshold (default 0.85)")
    ap.add_argument("--medium", type=float, default=MEDIUM_DEFAULT, help="medium-confidence threshold (default 0.50)")
    ap.add_argument("--categories",
                    help="flat-mode category definitions: {\"<name>\": {\"description\": str, "
                         "\"collections\": [ids]}} — validated strategy. Omit for tree-descent "
                         "mode (experimental: imprecise on trees with overlapping collections).")
    ap.add_argument("--probe", action="store_true",
                    help="print the environment verdict as JSON and exit (local checks only)")
    ap.add_argument("--probe-call", action="store_true",
                    help="with --probe: also send one tiny request to verify authentication")
    args = ap.parse_args()

    if args.probe:
        print(json.dumps(probe(do_auth_call=args.probe_call), ensure_ascii=False, indent=2))
        return
    if not args.collections or not args.bookmarks:
        ap.error("--collections and --bookmarks are required (unless running --probe)")
    if not 1 <= args.workers <= 32:
        ap.error("--workers must be between 1 and 32 (got %d)" % args.workers)
    if not 0.0 < args.medium < args.high <= 1.0:
        ap.error("thresholds must satisfy 0 < medium < high <= 1 "
                 "(got medium=%s, high=%s)" % (args.medium, args.high))

    verdict = probe()
    if verdict["opt_out"]:
        print(json.dumps({"jev": "disabled", "reason": "%s is set" % OPT_OUT_ENV}))
        return
    # Failure verdicts go to stdout (consistent with --probe output) plus a
    # nonzero exit code, so callers parsing stdout always see the reason.
    if not verdict["api_key"]:
        print(json.dumps({"jev": "not_configured", "reason": "TYPESAFE_API_KEY is not set"}), flush=True)
        sys.exit(1)
    if not verdict["sdk_available"]:
        print(json.dumps({"jev": "unavailable",
                          "reason": "typesafe-sdk import failed: %s" % verdict["sdk_error"]}), flush=True)
        sys.exit(1)
    if not verdict["python_ok"]:
        print(json.dumps({"jev": "unavailable",
                          "reason": "python >= 3.10 required, found %s" % verdict["python_version"]}), flush=True)
        sys.exit(1)

    collections = load_dump(args.collections, "collections")
    bookmarks = load_dump(args.bookmarks, "bookmarks")
    if args.limit:
        bookmarks = bookmarks[: args.limit]

    global by_id_local
    by_id, govable, tops, children = build_tree(collections)
    by_id_local = by_id
    known = {c.get("collection_id") for c in govable}
    categories = None
    if args.categories:
        with open(args.categories, "r", encoding="utf-8") as f:
            raw = json.load(f)
        categories = raw.get("categories", raw)
        if not isinstance(categories, dict) or not categories:
            sys.exit("error: %s must contain a non-empty 'categories' object" % args.categories)
    mode = "flat" if categories else "tree"

    results, errors = [], []
    t0 = time.time()

    def work(bm):
        client = get_client()
        current = bm.get("collection_id")
        if mode == "flat":
            pred = classify_flat(client, bm, categories)
            mapped = pred["mapped"]
            candidate = current not in mapped
            predicted_title = ", ".join(
                (by_id.get(cid, {}) or {}).get("title", str(cid)) for cid in mapped)
            return {
                "bookmark_id": bm.get("bookmark_id"),
                "title": (bm.get("title") or "")[:80],
                "from": current,
                "predicted_category": pred["category"],
                "predicted": mapped,
                "predicted_title": predicted_title,
                "confidence": round(pred["confidence"], 3),
                "band": ("consistent" if not candidate else
                         "high" if pred["confidence"] >= args.high else
                         "medium" if pred["confidence"] >= args.medium else "low"),
                "calls": pred["calls"],
            }
        pred = classify(client, bm, tops, children)
        conf = pred["confidence"]
        if pred["predicted"] == current:
            band = "consistent"
        elif conf >= args.high:
            band = "high"
        elif conf >= args.medium:
            band = "medium"
        else:
            band = "low"
        return {
            "bookmark_id": bm.get("bookmark_id"),
            "title": (bm.get("title") or "")[:80],
            "from": current,
            "predicted": pred["predicted"],
            "predicted_title": (by_id.get(pred["predicted"], {}) or {}).get("title"),
            "stage1_tree": pred["stage1_tree"],
            "stage1_confidence": round(pred["stage1_confidence"], 3),
            "confidence": round(conf, 3),
            "band": band,
            "calls": pred["calls"],
        }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [(bm, pool.submit(work, bm)) for bm in bookmarks]
        done = 0
        for bm, fut in futs:
            try:
                results.append(fut.result(timeout=FUTURE_TIMEOUT))
            except FutureTimeoutError:
                errors.append({"bookmark_id": bm.get("bookmark_id"),
                               "error": "per-bookmark timeout after %ss" % FUTURE_TIMEOUT})
            except Exception as exc:  # noqa: BLE001
                errors.append({"bookmark_id": bm.get("bookmark_id"),
                               "error": str(exc)[:200]})
            done += 1
            if done % 25 == 0 or done == len(bookmarks):
                print("progress %d/%d errors=%d elapsed=%.0fs"
                      % (done, len(bookmarks), len(errors), time.time() - t0), flush=True)

    results.sort(key=lambda r: (r["band"] != "high", r["band"] != "medium",
                                -(r["confidence"])))
    bands = {}
    for r in results:
        bands[r["band"]] = bands.get(r["band"], 0) + 1
    calls_total = sum(r["calls"] for r in results)
    payload = {
        "mode": mode,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "thresholds": {"high": args.high, "medium": args.medium},
        "n_bookmarks": len(bookmarks),
        "n_results": len(results),
        "n_errors": len(errors),
        "partial_failure": bool(errors) and bool(results),
        "failed_bookmark_ids": [e.get("bookmark_id") for e in errors],
        "bands": bands,
        "jev_calls": calls_total,
        "elapsed_seconds": round(time.time() - t0, 1),
        "results": results,
        "errors": errors,
    }
    out_path = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.bookmarks)), "jev-precheck-results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("DONE bands=%s calls=%d -> %s" % (bands, calls_total, out_path))


if __name__ == "__main__":
    main()
