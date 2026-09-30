#!/usr/bin/env python3
"""Seeded HELD-OUT generator. Standard library only.

Ground truth is fixed BY CONSTRUCTION inside each template (derived from RESOLVER_RULES.md),
never by running the resolver. Writes heldout/claims.ndjson, heldout/expected_answers.json and
heldout/audit_sample.md (a blind sheet for hand-labeling a sample yourself).

Usage: python build_heldout.py [--seed 2026]
Freeze: commit heldout/ BEFORE the first official run. A different seed is a different test set.
"""
import argparse
import collections
import datetime
import json
import pathlib
import random

HERE = pathlib.Path(__file__).parent
OUT = HERE / "heldout"
SUBJECT = "heldout"
ASOF = "2026-09-19"
EPOCH = datetime.date(2024, 1, 1)

SCOPES = [("all", None), ("free", "all"), ("pro", "all"), ("enterprise", "all"),
          ("enterprise_eu", "enterprise"), ("enterprise_us", "enterprise"),
          ("new_configurations", "all"), ("legacy_configurations", "all")]
PLAN_SIBS = ["free", "pro", "enterprise"]
AGE_SIBS = ["new_configurations", "legacy_configurations"]
SOURCE_TYPES = ["product_guide", "release_notes", "faq", "migration_guide", "admin_guide", "errata"]


def R(_id):
    return {"_type": "reference", "_ref": _id}


def ans(scope, value, *claim_ids):
    return {"scope": scope, "value": value, "claims": sorted(claim_ids)}


def shift(d, days):
    return (datetime.date.fromisoformat(d) + datetime.timedelta(days=days)).isoformat()


def mid(d1, d2):
    a, b = datetime.date.fromisoformat(d1), datetime.date.fromisoformat(d2)
    return (a + (b - a) // 2).isoformat()


class Builder:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.claims, self.questions = [], []
        self.n_attr = self.n_claim = self.n_q = 0
        self.attr = self.template = None

    def new_attr(self, template):
        self.n_attr += 1
        self.template, self.attr = template, f"h_metric_{self.n_attr:03d}"

    def values(self, k):
        return self.rng.sample(range(5, 900), k)

    def dates(self, k):
        """k strictly increasing dates, at least 10 days apart, all well before ASOF."""
        return [(EPOCH + datetime.timedelta(days=o)).isoformat()
                for o in sorted(self.rng.sample(range(0, 900, 10), k))]

    def future(self):
        return shift("2026-10-01", self.rng.randint(0, 240))

    def scope(self):
        return self.rng.choice(["all"] + PLAN_SIBS + AGE_SIBS)

    def claim(self, value, scope, date, sup=()):
        """sup = [(target_claim_id, inScope_or_None)]. Version is random and independent of date."""
        self.n_claim += 1
        cid = f"claim-h{self.n_claim:03d}"
        self.claims.append({
            "id": cid, "attribute": self.attr, "value": value, "scope": scope, "effectiveFrom": date,
            "version": f"{self.rng.randint(1, 4)}.{self.rng.randint(0, 3)}",
            "supersedes": [{"claim": t, "inScope": s} for t, s in sup],
            "sourceType": self.rng.choice(SOURCE_TYPES),
        })
        return cid

    def q(self, scope, asof, status, answers=(), excluded=None, ineligible=(), reason=None,
          headline=True, tags=()):
        self.n_q += 1
        self.questions.append({
            "id": f"h{self.n_q:03d}", "template": self.template, "cluster": self.attr,
            "headline": headline, "tags": list(tags),
            "query": {"subject": SUBJECT, "attribute": self.attr, "scope": scope, "asOf": asof},
            "expected": {"status": status, "answers": list(answers), "excluded": excluded or {},
                         "ineligible": sorted(ineligible), "reason": reason},
        })


# ---------------------------------------------------------------- templates (truth by construction)

def t_single(b):
    b.new_attr("single")
    s, v, d = b.scope(), b.values(1)[0], b.dates(1)[0]
    ids = [b.claim(v, s, d)] + ([b.claim(v, s, d)] if b.rng.random() < 0.5 else [])
    b.q(s, ASOF, "supported", [ans(s, v, *ids)])


def t_agree_dates(b):  # same value, different dates/versions, no link: NOT a conflict
    b.new_attr("agree_diff_dates")
    v, (d1, d2) = b.values(1)[0], b.dates(2)
    c1, c2 = b.claim(v, "all", d1), b.claim(v, "all", d2)
    b.q("all", ASOF, "supported", [ans("all", v, c1, c2)])


def t_chain(b):  # explicit supersession chain, dates increasing
    b.new_attr("chain")
    k = b.rng.choice([2, 3])
    vs, ds, ids = b.values(k), b.dates(k), []
    for i in range(k):
        ids.append(b.claim(vs[i], "all", ds[i], [(ids[-1], "all")] if ids else []))
    b.q("all", ASOF, "superseded", [ans("all", vs[-1], ids[-1])],
        {ids[i]: f"superseded_by:{ids[i + 1]}" for i in range(k - 1)})
    m = mid(ds[-2], ds[-1])
    if k == 2:
        b.q("all", m, "supported", [ans("all", vs[0], ids[0])], ineligible=[ids[1]])
    else:
        b.q("all", m, "superseded", [ans("all", vs[1], ids[1])],
            {ids[0]: f"superseded_by:{ids[1]}"}, ineligible=[ids[2]])
    b.q("all", shift(ds[0], -30), "insufficient", ineligible=ids, reason="not_yet_effective")


def t_same_date_super(b):  # explicit supersession with equal dates: superseded, not "tie"
    b.new_attr("same_date_supersession")
    (v1, v2), d = b.values(2), b.dates(1)[0]
    c1 = b.claim(v1, "all", d)
    c2 = b.claim(v2, "all", d, [(c1, "all")])
    b.q("all", ASOF, "superseded", [ans("all", v2, c2)], {c1: f"superseded_by:{c2}"})


def t_retro(b):  # retroactive correction: the replacement is OLDER than the claim it supersedes
    b.new_attr("retroactive_correction")
    (v_bad, v_fix), (d_fix, d_bad) = b.values(2), b.dates(2)
    bad = b.claim(v_bad, "all", d_bad)
    fix = b.claim(v_fix, "all", d_fix, [(bad, "all")])
    b.q("all", ASOF, "superseded", [ans("all", v_fix, fix)], {bad: f"superseded_by:{fix}"})
    b.q("all", mid(d_fix, d_bad), "supported", [ans("all", v_fix, fix)], ineligible=[bad])
    b.q("all", shift(d_fix, -30), "insufficient", ineligible=[bad, fix], reason="not_yet_effective")


def t_newer_unlinked(b):  # newer value, NO supersedes link: conflict, not "newest wins"
    b.new_attr("newer_value_no_link")
    s, (a, v2), (d1, d2) = b.scope(), b.values(2), b.dates(2)
    old, new = b.claim(a, s, d1), b.claim(v2, s, d2)
    b.q(s, ASOF, "conflicting", [ans(s, a, old), ans(s, v2, new)])
    b.q(s, mid(d1, d2), "supported", [ans(s, a, old)], ineligible=[new])


def t_same_date_conflict(b):
    b.new_attr("same_date_conflict")
    k, s, d = b.rng.choice([2, 3]), b.scope(), b.dates(1)[0]
    vs = b.values(k)
    b.q(s, ASOF, "conflicting", [ans(s, v, b.claim(v, s, d)) for v in vs])


def t_contextual(b):  # sibling scopes, no claim at "all": contextual for Q=all
    b.new_attr("contextual_siblings")
    plan_based = b.rng.random() < 0.5
    sibs = b.rng.sample(PLAN_SIBS, b.rng.choice([2, 3])) if plan_based else list(AGE_SIBS)
    vs = b.values(len(sibs))
    answers = [ans(s, v, b.claim(v, s, b.dates(1)[0])) for s, v in zip(sibs, vs)]
    b.q("all", ASOF, "contextual", answers)
    i = b.rng.randrange(len(sibs))
    b.q(sibs[i], ASOF, "supported", [answers[i]])
    absent = [s for s in PLAN_SIBS if s not in sibs] if plan_based else []
    if absent:
        b.q(absent[0], ASOF, "insufficient", reason="no_applicable_claim")


def t_broad_narrow(b):  # narrower scope overrides broader only inside its own scope
    b.new_attr("broad_narrow")
    deep = b.rng.random() < 0.4
    vs, ds = b.values(3), [b.dates(1)[0] for _ in range(3)]
    broad, ent = b.claim(vs[0], "all", ds[0]), b.claim(vs[1], "enterprise", ds[1])
    ov = lambda s: f"overridden_by_narrower_scope:{s}"
    b.q("free", ASOF, "supported", [ans("all", vs[0], broad)])
    b.q("enterprise_us" if deep else "enterprise", ASOF, "supported", [ans("enterprise", vs[1], ent)],
        {broad: ov("enterprise")})
    if deep:
        eu = b.claim(vs[2], "enterprise_eu", ds[2])
        b.q("enterprise_eu", ASOF, "supported", [ans("enterprise_eu", vs[2], eu)],
            {broad: ov("enterprise_eu"), ent: ov("enterprise_eu")})
        b.q("enterprise", ASOF, "unsupported_case", headline=False, tags=["tier2"])
    b.q("all", ASOF, "unsupported_case", headline=False, tags=["tier2"])


def t_narrow_conflict(b):  # conflict inside the narrow scope; the broad claim cannot resolve it
    b.new_attr("narrow_scope_conflict")
    (va, v1, v2), d = b.values(3), b.dates(1)[0]
    broad = b.claim(va, "all", b.dates(1)[0])
    c1, c2 = b.claim(v1, "enterprise", d), b.claim(v2, "enterprise", d)
    b.q("enterprise", ASOF, "conflicting", [ans("enterprise", v1, c1), ans("enterprise", v2, c2)],
        {broad: "overridden_by_narrower_scope:enterprise"})
    b.q("free", ASOF, "supported", [ans("all", va, broad)])


def t_partial_super(b):  # supersession that applies only inside its inScope
    b.new_attr("partial_supersession")
    s, o = (b.rng.sample(PLAN_SIBS, 2) if b.rng.random() < 0.5 else b.rng.sample(AGE_SIBS, 2))
    (a, v2), (d1, d2) = b.values(2), b.dates(2)
    old = b.claim(a, "all", d1)
    new = b.claim(v2, s, d2, [(old, s)])
    b.q(s, ASOF, "superseded", [ans(s, v2, new)], {old: f"superseded_by:{new}"})
    b.q(o, ASOF, "supported", [ans("all", a, old)])
    b.q(s, mid(d1, d2), "supported", [ans("all", a, old)], ineligible=[new])
    b.q("all", ASOF, "unsupported_case", headline=False, tags=["tier2"])


def t_insufficient(b, kind):
    b.new_attr(f"insufficient_{kind}")
    if kind == "no_claims":
        b.q("all", ASOF, "insufficient", reason="no_claims")
    elif kind == "not_yet_effective":
        c = b.claim(b.values(1)[0], "all", b.future())
        b.q("all", ASOF, "insufficient", ineligible=[c], reason="not_yet_effective")
    else:
        b.claim(b.values(1)[0], "enterprise", b.dates(1)[0])
        b.q("free", ASOF, "insufficient", reason="no_applicable_claim")


def t_missing_scope(b):  # Rule 4: a missing scope is unknown, never "all"
    b.new_attr("missing_scope_alone")
    b.claim(b.values(1)[0], None, b.dates(1)[0])
    b.q("all", ASOF, "insufficient", reason="no_applicable_claim", tags=["degraded"])
    b.new_attr("missing_scope_with_valid")
    (a, v2), (d1, d2) = b.values(2), b.dates(2)
    valid = b.claim(a, "all", d1)
    b.claim(v2, None, d2)
    b.q("all", ASOF, "supported", [ans("all", a, valid)], tags=["degraded"])


def t_missing_date(b):  # Rule 4: a missing date is unknown, never "current"
    b.new_attr("missing_date_alone")
    b.claim(b.values(1)[0], "all", None)
    b.q("all", ASOF, "insufficient", reason="unknown_metadata", tags=["degraded"])
    b.new_attr("missing_date_with_valid")
    (a, v2), d = b.values(2), b.dates(1)[0]
    valid = b.claim(a, "all", d)
    b.claim(v2, "all", None)
    b.q("all", ASOF, "supported", [ans("all", a, valid)], tags=["degraded"])


def t_null_inscope_link(b):  # Rule 4: a supersession link with unknown inScope establishes nothing
    b.new_attr("supersession_unknown_inscope")
    (a, v2), (d1, d2) = b.values(2), b.dates(2)
    c1 = b.claim(a, "all", d1)
    c2 = b.claim(v2, "all", d2, [(c1, None)])
    b.q("all", ASOF, "conflicting", [ans("all", a, c1), ans("all", v2, c2)], tags=["degraded"])


PLAN = [(t_single, 14), (t_agree_dates, 8), (t_chain, 10), (t_same_date_super, 6), (t_retro, 8),
        (t_newer_unlinked, 12), (t_same_date_conflict, 12), (t_contextual, 40), (t_broad_narrow, 10),
        (t_narrow_conflict, 8), (t_partial_super, 10), (t_missing_scope, 18), (t_missing_date, 18),
        (t_null_inscope_link, 18)] + [
    (lambda b, k=k: t_insufficient(b, k), 4) for k in ("no_claims", "not_yet_effective", "wrong_scope")]


# ---------------------------------------------------------------- output

def to_docs(b):
    docs = []
    for sid, parent in SCOPES:
        d = {"_id": f"scope-{sid}", "_type": "scope", "scopeId": sid}
        if parent:
            d["parent"] = R(f"scope-{parent}")
        docs.append(d)
    for c in b.claims:
        d = {"_id": c["id"], "_type": "claim", "claimId": c["id"].removeprefix("claim-"),
             "subject": SUBJECT, "attribute": c["attribute"], "value": c["value"], "unit": "units"}
        if c["scope"]:
            d["scope"] = R(f"scope-{c['scope']}")
        d["version"] = c["version"]
        if c["effectiveFrom"]:
            d["effectiveFrom"] = c["effectiveFrom"]
        if c["supersedes"]:
            d["supersedes"] = []
            for i, s in enumerate(c["supersedes"]):
                item = {"_key": f"{c['id']}-s{i}", "_type": "supersession", "claim": R(s["claim"])}
                if s["inScope"]:
                    item["inScope"] = R(f"scope-{s['inScope']}")
                d["supersedes"].append(item)
        d["sourceId"] = f"src-{c['id'][-4:]}"
        d["sourceType"] = c["sourceType"]
        docs.append(d)
    return docs


def check(b, docs):
    ids = {d["_id"] for d in docs}
    assert len(ids) == len(docs), "duplicate _id"
    by_id = {c["id"]: c for c in b.claims}
    for d in docs:
        if "effectiveFrom" in d:
            datetime.date.fromisoformat(d["effectiveFrom"])
        for key in ("scope", "parent"):
            if key in d:
                assert d[key]["_ref"] in ids, f"dangling {key} on {d['_id']}"
        for s in d.get("supersedes", []):
            assert s["claim"]["_ref"] in ids and ("inScope" not in s or s["inScope"]["_ref"] in ids)
            assert by_id[s["claim"]["_ref"]]["attribute"] == d["attribute"], "cross-attribute link"
    assert len({q["id"] for q in b.questions}) == len(b.questions)
    for q in b.questions:
        datetime.date.fromisoformat(q["query"]["asOf"])
        e = q["expected"]
        cited = [c for a in e["answers"] for c in a["claims"]] + list(e["excluded"]) + e["ineligible"]
        for c in cited:
            assert by_id[c]["attribute"] == q["cluster"], f"{q['id']} cites another cluster's claim"
        for a in e["answers"]:
            assert all(by_id[c]["value"] == a["value"] for c in a["claims"]), f"{q['id']} value mismatch"


def audit_sheet(b, seed):
    rng = random.Random(seed + 1)
    head = [q for q in b.questions if q["headline"]]
    picked = [rng.choice([q for q in head if q["template"] == t])
              for t in sorted({q["template"] for q in head})]
    rest = [q for q in head if q not in picked]
    picked += rng.sample(rest, max(0, 36 - len(picked)))
    rng.shuffle(picked)
    by_attr = collections.defaultdict(list)
    for c in b.claims:
        by_attr[c["attribute"]].append(c)
    lines = ["# Blind audit sheet (label these yourself, BEFORE looking at expected_answers.json)", "",
             "Statuses: SUPPORTED, SUPERSEDED, CONTEXTUAL, CONFLICTING, INSUFFICIENT, UNSUPPORTED "
             "(question scope has a claim covering it AND claims in narrower scopes below it).", "",
             "Apply only RESOLVER_RULES.md. `all` > `free`, `pro`, `enterprise` (> `enterprise_eu`, "
             "`enterprise_us`), `new_configurations`, `legacy_configurations`. MISSING means unknown.", ""]
    for q in picked:
        qq = q["query"]
        lines += [f"## {q['id']}: scope `{qq['scope']}`, as of `{qq['asOf']}`", "",
                  "| claim | value | scope | version | effectiveFrom | supersedes (target @ inScope) |",
                  "|---|---|---|---|---|---|"]
        for c in by_attr[q["cluster"]]:
            sup = ", ".join(f"{s['claim']} @ {s['inScope'] or 'MISSING'}" for s in c["supersedes"]) or "-"
            lines.append(f"| {c['id']} | {c['value']} | {c['scope'] or 'MISSING'} | {c['version']} | "
                         f"{c['effectiveFrom'] or 'MISSING'} | {sup} |")
        lines += ["", "Your answer: status ______  value(s) ______", ""]
    (OUT / "audit_sample.md").write_text("\n".join(lines), encoding="utf-8")
    return len(picked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    seed = ap.parse_args().seed
    b = Builder(seed)
    jobs = [fn for fn, n in PLAN for _ in range(n)]
    b.rng.shuffle(jobs)
    for fn in jobs:
        fn(b)
    docs = to_docs(b)
    check(b, docs)

    OUT.mkdir(exist_ok=True)
    with open(OUT / "claims.ndjson", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    head = [q for q in b.questions if q["headline"]]
    meta = {"set": "heldout_v1", "held_out": True, "seed": seed, "defaultAsOf": ASOF, "rules": "RESOLVER_RULES.md",
            "statuses": ["supported", "contextual", "conflicting", "superseded", "insufficient", "unsupported_case"],
            "note": "Truth is fixed by template construction, not by running the resolver."}
    with open(OUT / "expected_answers.json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "questions": b.questions}, f, indent=2)
    n_audit = audit_sheet(b, seed)

    by_status = collections.Counter(q["expected"]["status"] for q in head)
    degraded = sum(1 for c in b.claims if c["scope"] is None or c["effectiveFrom"] is None
                   or any(s["inScope"] is None for s in c["supersedes"]))
    print(f"seed={seed}: {len(docs)} docs ({len(SCOPES)} scopes, {len(b.claims)} claims, {b.n_attr} clusters), "
          f"{len(b.questions)} questions ({len(head)} headline, {len(b.questions) - len(head)} tier-2)")
    print("headline truth:", dict(sorted(by_status.items())))
    print(f"degraded-metadata claims: {degraded}/{len(b.claims)} = {degraded / len(b.claims):.0%}")
    print(f"audit sheet: {n_audit} questions -> heldout/audit_sample.md")


if __name__ == "__main__":
    main()
