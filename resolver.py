#!/usr/bin/env python3
"""System C: contextual conflict resolver. Standard library only.

Implements RESOLVER_RULES.md. Input is normalized claim dicts, so the same code
runs on the local NDJSON fixtures or on results fetched from Sanity Context.
"""
import json

# Retrieval lives in mcp_client.py. groq_query takes only a query string (no $params),
# so those queries inline validated identifiers. Rule logic below is unchanged.


def load_local(path):
    """Read claims.ndjson into (claims, scope_parent) in the normalized shape."""
    with open(path, encoding="utf-8") as f:
        docs = [json.loads(line) for line in f if line.strip()]

    def scope_of(ref):
        return ref["_ref"].removeprefix("scope-") if ref else None

    parent = {d["scopeId"]: scope_of(d.get("parent")) for d in docs if d["_type"] == "scope"}
    claims = [
        {
            "id": d["_id"], "subject": d["subject"], "attribute": d["attribute"],
            "value": d["value"], "scope": scope_of(d.get("scope")),
            "version": d.get("version"), "effectiveFrom": d.get("effectiveFrom"),
            "supersedes": [
                {"claim": s["claim"]["_ref"], "inScope": scope_of(s.get("inScope"))}
                for s in d.get("supersedes", [])
            ],
        }
        for d in docs if d["_type"] == "claim"
    ]
    return claims, parent


def ancestors(scope, parent):
    """[scope, its parent, ..., root]. Unknown or None scope gives []."""
    out, seen = [], set()
    while scope is not None and scope not in seen:
        out.append(scope)
        seen.add(scope)
        scope = parent.get(scope)
    return out


def _result(status, answers=(), excluded=None, ineligible=(), reason=None):
    return {"status": status, "answers": list(answers), "excluded": dict(excluded or {}),
            "ineligible": sorted(ineligible), "reason": reason}


def _group(claims):
    groups = {}
    for c in claims:
        groups.setdefault((c["scope"], c["value"]), []).append(c["id"])
    return [{"scope": s, "value": v, "claims": sorted(ids)}
            for (s, v), ids in sorted(groups.items(), key=lambda kv: (kv[0][0] or "", kv[0][1]))]


def _below(eligible, q_scope, parent):
    """Scopes strictly below q_scope that hold eligible claims."""
    return sorted({c["scope"] for c in eligible
                   if c["scope"] and c["scope"] != q_scope and q_scope in ancestors(c["scope"], parent)})


def resolve(claims, parent, q):
    """q = {"subject", "attribute", "scope", "asOf"}. Returns a structured result."""
    pool = [c for c in claims if c["subject"] == q["subject"] and c["attribute"] == q["attribute"]]
    if not pool:
        return _result("insufficient", reason="no_claims")

    # Rule 3 + Rule 4: a missing date is unknown, so the claim is not eligible.
    future = [c["id"] for c in pool if c["effectiveFrom"] and c["effectiveFrom"] > q["asOf"]]
    eligible = [c for c in pool if c["effectiveFrom"] and c["effectiveFrom"] <= q["asOf"]]
    if not eligible:
        return _result("insufficient", ineligible=future,
                       reason="not_yet_effective" if future else "unknown_metadata")

    # Rule 4: a missing scope is never in the ancestor list, so it is never applicable.
    anc = ancestors(q["scope"], parent)
    applicable = [c for c in eligible if c["scope"] in anc]
    below = _below(eligible, q["scope"], parent)

    if not applicable:
        if not below:
            return _result("insufficient", ineligible=future, reason="no_applicable_claim")
        subs = [resolve(claims, parent, {**q, "scope": s}) for s in below]
        if any(s["status"] not in ("supported", "superseded") for s in subs):
            raise NotImplementedError("contextual split with a non-resolved child (RESOLVER_RULES open item 2)")
        answers = sorted((a for s in subs for a in s["answers"]), key=lambda a: (a["scope"] or "", a["value"]))
        excluded = {k: v for s in subs for k, v in s["excluded"].items()}
        return _result("contextual", answers, excluded, future)

    if below:
        raise NotImplementedError("applicable claims plus descendant-scope claims (RESOLVER_RULES open item 2)")

    # Rule 1: only explicit links from eligible claims make a claim stale, and only
    # within the link's inScope. Stale claims keep their own power to supersede.
    stale = {}
    for y in eligible:
        for link in y["supersedes"]:
            if link["inScope"] in anc:
                stale.setdefault(link["claim"], []).append(y["id"])
    excluded, live = {}, []
    for c in applicable:
        if c["id"] in stale:
            excluded[c["id"]] = "superseded_by:" + sorted(stale[c["id"]])[0]
        else:
            live.append(c)
    if not live:
        return _result("insufficient", excluded=excluded, ineligible=future, reason="all_claims_superseded")

    # Rule 2: the narrowest applicable scope wins for this question's scope.
    top = max(len(ancestors(c["scope"], parent)) for c in live)
    deepest = [c for c in live if len(ancestors(c["scope"], parent)) == top]
    for c in live:
        if c not in deepest:
            excluded[c["id"]] = f"overridden_by_narrower_scope:{deepest[0]['scope']}"

    # Same narrowest scope, different values, no link between them: conflict.
    # (Assumes open item 1: no "same version/date" qualifier, because Rule 1 forbids recency.)
    if len({c["value"] for c in deepest}) > 1:
        status = "conflicting"
    elif any(v.startswith("superseded_by") for v in excluded.values()):
        status = "superseded"
    else:
        status = "supported"
    return _result(status, _group(deepest), excluded, future)
