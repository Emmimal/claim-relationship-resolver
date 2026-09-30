#!/usr/bin/env python3
"""Score the resolver against expected_answers.json. Standard library only.

Usage: python evaluate.py [--dir DIR]     (DIR holds claims.ndjson + expected_answers.json)
Each layer is scored separately so a failure is attributed to the right stage.
Tier-2 questions (headline=false) are scored on the layers but kept out of the conflict rates.
"""
import argparse
import json
import math
import pathlib
import sys

from resolver import load_local, resolve

HERE = pathlib.Path(__file__).parent


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def layers(exp, got):
    key = lambda r: sorted((a["scope"] or "", a["value"]) for a in r["answers"])
    full = lambda r: sorted((a["scope"] or "", a["value"], tuple(sorted(a["claims"]))) for a in r["answers"])
    return {
        "status": exp["status"] == got["status"],
        "values+scopes": key(exp) == key(got),
        "source_attribution": full(exp) == full(got),
        "exclusions": exp["excluded"] == got["excluded"],
        "ineligible": sorted(exp["ineligible"]) == sorted(got["ineligible"]),
        "reason": exp["reason"] == got["reason"],
    }


def rate(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.2f}  (95% Wilson {lo:.2f}-{hi:.2f})" if n else "n/a (0 cases)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    base = HERE / ap.parse_args().dir
    claims, parent = load_local(base / "claims.ndjson")
    data = json.load(open(base / "expected_answers.json", encoding="utf-8"))
    qs = data["questions"]

    totals, exact, failures, rows = {}, 0, [], []
    for item in qs:
        try:
            got = resolve(claims, parent, item["query"])
        except NotImplementedError:  # tier-2: reported, never invented
            got = {"status": "unsupported_case", "answers": [], "excluded": {}, "ineligible": [], "reason": None}
        ok = layers(item["expected"], got)
        for name, v in ok.items():
            totals[name] = totals.get(name, 0) + v
        exact += all(ok.values())
        if item.get("headline", True):
            rows.append((item["expected"]["status"], got["status"]))
        bad = [n for n, v in ok.items() if not v]
        if bad:
            failures.append((item["id"], item.get("template", ""), f"layers failed: {bad}"))

    n = len(qs)
    print(f"set={data['meta']['set']} held_out={data['meta']['held_out']} questions={n}")
    print(f"exact match: {rate(exact, n)}")
    for name in ["status", "values+scopes", "source_attribution", "exclusions", "ineligible", "reason"]:
        print(f"  {name:<20} {rate(totals.get(name, 0), n)}")
    not_conf = [r for r in rows if r[0] != "conflicting"]
    conf = [r for r in rows if r[0] == "conflicting"]
    print(f"false conflict rate  {rate(sum(r[1] == 'conflicting' for r in not_conf), len(not_conf))}")
    print(f"missed conflict rate {rate(sum(r[1] != 'conflicting' for r in conf), len(conf))}")
    for qid, tpl, msg in failures:
        print(f"FAIL {qid} [{tpl}]: {msg}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
