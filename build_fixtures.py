#!/usr/bin/env python3
"""Batch-1 DEVELOPMENT fixtures for the contextual-conflict benchmark.

Writes claims.ndjson (import with the Sanity CLI) and expected_answers.json.
Standard library only. Run: python build_fixtures.py
These are dev fixtures for building the resolver. They are NOT the held-out set.
"""
import datetime
import json
import pathlib

OUT = pathlib.Path(__file__).parent
SUBJECT = "platform"
DEFAULT_ASOF = "2026-09-19"

# Version -> effectiveFrom. Stored explicitly on every claim; the resolver must
# never derive a date from a version string (Rule 3).
VERSION_DATE = {"1.0": "2025-01-01", "1.1": "2026-03-01", "2.0": "2026-09-01", "3.0": "2027-01-01"}

# (scopeId, parent). One dimension per cluster in batch 1.
SCOPES = [
    ("all", None),
    ("free", "all"),
    ("enterprise", "all"),
    ("new_configurations", "all"),
    ("legacy_configurations", "all"),
]

# (claimId, attribute, value, unit, scope, version, sourceId, sourceType, supersedes[(claimId, inScope)])
CLAIMS = [
    ("c01", "max_projects", 100, "projects", "all", "1.0", "product-guide-1.0", "product_guide", []),
    ("c02", "max_projects", 100, "projects", "all", "1.0", "faq-1.0", "faq", []),
    ("c03", "timeout_s", 30, "seconds", "all", "1.0", "product-guide-1.0", "product_guide", []),
    ("c04", "timeout_s", 60, "seconds", "all", "1.1", "release-notes-1.1", "release_notes", [("c03", "all")]),
    ("c05", "rate_limit_rps", 10, "requests_per_second", "all", "1.0", "product-guide-1.0", "product_guide", []),
    ("c06", "rate_limit_rps", 20, "requests_per_second", "all", "1.1", "release-notes-1.1", "release_notes", [("c05", "all")]),
    ("c07", "rate_limit_rps", 50, "requests_per_second", "all", "2.0", "release-notes-2.0", "release_notes", [("c06", "all")]),
    ("c08", "max_items", 500, "items", "new_configurations", "2.0", "release-notes-2.0", "release_notes", []),
    ("c09", "max_items", 100, "items", "legacy_configurations", "2.0", "migration-guide-2.0", "migration_guide", []),
    ("c10", "retention_days", 30, "days", "all", "2.0", "product-guide-2.0", "product_guide", []),
    ("c11", "retention_days", 90, "days", "all", "2.0", "admin-guide-2.0", "admin_guide", []),
    ("c12", "payload_mb", 10, "megabytes", "all", "2.0", "product-guide-2.0", "product_guide", []),
    ("c13", "payload_mb", 25, "megabytes", "enterprise", "2.0", "admin-guide-2.0", "admin_guide", []),
    ("c14", "payload_mb", 15, "megabytes", "enterprise", "2.0", "release-notes-2.0", "release_notes", []),
    ("c15", "webhook_retries", 3, "retries", "all", "1.0", "product-guide-1.0", "product_guide", []),
    ("c16", "webhook_retries", 5, "retries", "new_configurations", "1.1", "release-notes-1.1", "release_notes", [("c15", "new_configurations")]),
    ("c17", "sso_seats", 50, "seats", "enterprise", "2.0", "admin-guide-2.0", "admin_guide", []),
    ("c18", "audit_days", 365, "days", "all", "3.0", "release-notes-3.0", "release_notes", []),
]


def ref(kind, ident):
    # No dots in _id: in Sanity, ids containing "." are treated as private/path ids.
    return {"_type": "reference", "_ref": f"{kind}-{ident}"}


def build_docs():
    docs = []
    for sid, parent in SCOPES:
        d = {"_id": f"scope-{sid}", "_type": "scope", "scopeId": sid}
        if parent:
            d["parent"] = ref("scope", parent)
        docs.append(d)
    for cid, attr, val, unit, scope, ver, src, stype, sup in CLAIMS:
        d = {
            "_id": f"claim-{cid}", "_type": "claim", "claimId": cid,
            "subject": SUBJECT, "attribute": attr, "value": val, "unit": unit,
            "scope": ref("scope", scope), "version": ver,
            "effectiveFrom": VERSION_DATE[ver],
            "sourceId": src, "sourceType": stype,
        }
        if sup:
            d["supersedes"] = [
                {"_key": f"{cid}-s{i}", "_type": "supersession",
                 "claim": ref("claim", tgt), "inScope": ref("scope", ins)}
                for i, (tgt, ins) in enumerate(sup)
            ]
        docs.append(d)
    return docs


def ans(scope, value, *claims):
    return {"scope": scope, "value": value, "claims": [f"claim-{c}" for c in claims]}


def q(qid, attr, scope, status, answers, asof=DEFAULT_ASOF, excluded=None, ineligible=None, reason=None):
    return {
        "id": qid, "cluster": attr,
        "query": {"subject": SUBJECT, "attribute": attr, "scope": scope, "asOf": asof},
        "expected": {
            "status": status, "answers": answers,
            "excluded": excluded or {},
            "ineligible": [f"claim-{c}" for c in (ineligible or [])],
            "reason": reason,
        },
    }


QUESTIONS = [
    q("q01", "max_projects", "all", "supported", [ans("all", 100, "c01", "c02")]),
    q("q02", "timeout_s", "all", "superseded", [ans("all", 60, "c04")],
      asof="2026-06-01", excluded={"claim-c03": "superseded_by:claim-c04"}),
    q("q03", "timeout_s", "all", "supported", [ans("all", 30, "c03")],
      asof="2026-02-01", ineligible=["c04"]),
    q("q04", "rate_limit_rps", "all", "superseded", [ans("all", 50, "c07")],
      excluded={"claim-c05": "superseded_by:claim-c06", "claim-c06": "superseded_by:claim-c07"}),
    q("q05", "rate_limit_rps", "all", "superseded", [ans("all", 20, "c06")],
      asof="2026-05-01", excluded={"claim-c05": "superseded_by:claim-c06"}, ineligible=["c07"]),
    q("q06", "max_items", "all", "contextual",
      [ans("new_configurations", 500, "c08"), ans("legacy_configurations", 100, "c09")]),
    q("q07", "max_items", "legacy_configurations", "supported", [ans("legacy_configurations", 100, "c09")]),
    q("q08", "max_items", "new_configurations", "supported", [ans("new_configurations", 500, "c08")]),
    q("q09", "retention_days", "all", "conflicting", [ans("all", 30, "c10"), ans("all", 90, "c11")]),
    q("q10", "payload_mb", "enterprise", "conflicting",
      [ans("enterprise", 25, "c13"), ans("enterprise", 15, "c14")],
      excluded={"claim-c12": "overridden_by_narrower_scope:enterprise"}),
    q("q11", "payload_mb", "free", "supported", [ans("all", 10, "c12")]),
    q("q12", "webhook_retries", "new_configurations", "superseded", [ans("new_configurations", 5, "c16")],
      excluded={"claim-c15": "superseded_by:claim-c16"}),
    q("q13", "webhook_retries", "legacy_configurations", "supported", [ans("all", 3, "c15")]),
    q("q14", "sso_seats", "free", "insufficient", [], reason="no_applicable_claim"),
    q("q15", "sso_seats", "enterprise", "supported", [ans("enterprise", 50, "c17")]),
    q("q16", "audit_days", "all", "insufficient", [], ineligible=["c18"], reason="not_yet_effective"),
    q("q17", "audit_days", "all", "supported", [ans("all", 365, "c18")], asof="2027-02-01"),
    q("q18", "max_users", "all", "insufficient", [], reason="no_claims"),
]


def check(docs):
    ids = {d["_id"] for d in docs}
    claims = {d["_id"]: d for d in docs if d["_type"] == "claim"}
    assert len(ids) == len(docs), "duplicate _id"
    for d in docs:
        datetime.date.fromisoformat(d.get("effectiveFrom", "2000-01-01"))
        for key in ("scope", "parent", "claim", "inScope"):
            if key in d:
                assert d[key]["_ref"] in ids, f"dangling {key} on {d['_id']}"
        for s in d.get("supersedes", []):
            tgt = claims[s["claim"]["_ref"]]
            assert (tgt["subject"], tgt["attribute"]) == (d["subject"], d["attribute"]), f"cross-attribute supersession {d['_id']}"
            assert s["inScope"]["_ref"] in ids
    for item in QUESTIONS:
        datetime.date.fromisoformat(item["query"]["asOf"])
        e = item["expected"]
        cited = [c for a in e["answers"] for c in a["claims"]] + list(e["excluded"]) + e["ineligible"]
        for c in cited:
            assert c in claims, f"{item['id']} cites unknown {c}"
        for a in e["answers"]:
            for c in a["claims"]:
                assert claims[c]["value"] == a["value"], f"{item['id']} value mismatch for {c}"
    assert len({i["id"] for i in QUESTIONS}) == len(QUESTIONS)


def main():
    docs = build_docs()
    check(docs)
    with open(OUT / "claims.ndjson", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    meta = {"set": "dev_batch_1", "held_out": False, "defaultAsOf": DEFAULT_ASOF,
            "rules": "RESOLVER_RULES.md", "statuses": ["supported", "contextual", "conflicting", "superseded", "insufficient"]}
    with open(OUT / "expected_answers.json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "questions": QUESTIONS}, f, indent=2)
    print(f"{len(docs)} documents ({len(SCOPES)} scopes, {len(CLAIMS)} claims), {len(QUESTIONS)} questions - checks passed")


if __name__ == "__main__":
    main()
