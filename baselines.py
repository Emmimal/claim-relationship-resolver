#!/usr/bin/env python3
"""Pre-registered baselines A, B and B+scope. Standard library only.

None use supersession links, so they share no hidden rule with the resolver.
Ties on the newest date are never broken: all tied claims are returned, and if
their values differ the status is "unresolved" (conflict not explicitly handled).
Baseline A (retrieval only) is deferred until natural-language question text exists.
"""
from resolver import ancestors


def _eligible(claims, q):
    return [c for c in claims
            if (c["subject"], c["attribute"]) == (q["subject"], q["attribute"])
            and c["effectiveFrom"] and c["effectiveFrom"] <= q["asOf"]]


def _newest(cands):
    if not cands:
        return {"status": "none", "answers": []}
    newest = max(c["effectiveFrom"] for c in cands)
    tied = [c for c in cands if c["effectiveFrom"] == newest]
    groups = {}
    for c in tied:
        groups.setdefault((c["scope"], c["value"]), []).append(c["id"])
    answers = [{"scope": s, "value": v, "claims": sorted(ids)}
               for (s, v), ids in sorted(groups.items(), key=lambda kv: (kv[0][0] or "", kv[0][1]))]
    return {"status": "answer" if len({c["value"] for c in tied}) == 1 else "unresolved", "answers": answers}


def baseline_b(claims, parent, q):
    """Newest wins: as-of eligible claims, scope-blind, newest effectiveFrom."""
    return _newest(_eligible(claims, q))


def baseline_b_scope(claims, parent, q):
    """Scope filter, then narrowest applicable scope, then newest effectiveFrom."""
    anc = ancestors(q["scope"], parent)
    cands = [c for c in _eligible(claims, q) if c["scope"] in anc]
    if cands:
        top = max(len(ancestors(c["scope"], parent)) for c in cands)
        cands = [c for c in cands if len(ancestors(c["scope"], parent)) == top]
    return _newest(cands)


# ---------------------------------------------------------------- Baseline A: retrieval only

def baseline_a(all_claims, index, q):
    """BM25 over question_text.phrase(q) against the WHOLE corpus (any subject/attribute),
    rendered as prose (corpus.render), with no relationship reasoning and no structured filter.
    Returns the single top-ranked document's value, unaltered by scope containment,
    supersession, or conflict detection -- this is what a plain keyword search would hand back.
    `index` is a BM25 instance pre-built over `all_claims` (see compare.py); passed in so the
    O(corpus) fit happens once per run, not once per question.
    """
    from question_text import question_tokens
    ranked = index.score(question_tokens(q))
    if not ranked:
        return {"status": "none", "answers": [], "hit_id": None}
    top_id, _ = ranked[0]
    top = next(c for c in all_claims if c["id"] == top_id)
    return {"status": "answer", "answers": [{"scope": top["scope"], "value": top["value"], "claims": [top_id]}],
            "hit_id": top_id, "hit_attribute": top["attribute"]}
