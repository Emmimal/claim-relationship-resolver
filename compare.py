#!/usr/bin/env python3
"""Run the frozen resolver and the baselines through one claim source.

Usage: python compare.py [--source local|mock|live] [--mock-sse] [--dir DIR]
  DIR holds claims.ndjson + expected_answers.json (default: the dev fixtures; use heldout for the held-out set).
  live needs SANITY_CONTEXT_MCP_URL and SANITY_ORGANIZATION_TOKEN in the environment (never on the command line).
For a non-local source the resolver's results are also checked for parity with the local run.
Report counts, never "accuracy". Questions inside one cluster share claims, so they are not independent.
"""
import argparse
import json
import os
import pathlib
import sys

from baselines import baseline_a, baseline_b, baseline_b_scope
from bm25 import BM25
from corpus import build_documents
from evaluate import rate
from mcp_client import SanityContextSource
from mock_mcp_server import start_mock
from resolver import load_local, resolve

HERE = pathlib.Path(__file__).parent
SINGLE = ("supported", "superseded")
COMMITTED = ("supported", "superseded", "contextual", "answer")  # the system committed to an answer


class LocalSource:
    def __init__(self, path):
        self.claims, self.parent = load_local(path)
        self.calls, self.seconds = 0, 0.0

    def fetch(self, q):
        return self.claims, self.parent

    def fetch_all(self, subject):
        return [c for c in self.claims if c["subject"] == subject], self.parent


def answer(source, system, q):
    claims, parent = source.fetch(q)
    try:
        return system(claims, parent, q)
    except NotImplementedError as e:  # never invent an answer for a tier-2 case
        return {"status": "unsupported_case", "answers": [], "excluded": {}, "ineligible": [], "reason": str(e)}


def is_correct(truth, pred):
    """One rule for every system. Baseline 'answer' counts as a single-valued answer."""
    ts, ps = truth["status"], pred["status"]
    pv = {a["value"] for a in pred["answers"]}
    key = lambda r: sorted((a["scope"] or "", a["value"]) for a in r["answers"])
    if ts == "unsupported_case":
        return ps == "unsupported_case"
    if ts in SINGLE:
        return ps in ("supported", "superseded", "answer") and pv == {truth["answers"][0]["value"]}
    if ts == "contextual":
        return ps == "contextual" and key(truth) == key(pred)
    if ts == "conflicting":
        return ps == "conflicting" and pv == {a["value"] for a in truth["answers"]}
    return ps in ("insufficient", "none")  # truth is insufficient


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["local", "mock", "live"], default="local")
    ap.add_argument("--mock-sse", action="store_true")
    ap.add_argument("--dir", default=".")
    args = ap.parse_args()
    base = HERE / args.dir
    claims_path = base / "claims.ndjson"
    data = json.load(open(base / "expected_answers.json", encoding="utf-8"))
    qs = data["questions"]
    head = [i for i, it in enumerate(qs) if it.get("headline", True)]
    tier2 = [i for i, it in enumerate(qs) if not it.get("headline", True)]

    server = None
    if args.source == "local":
        src = LocalSource(claims_path)
    elif args.source == "mock":
        server, url = start_mock(claims_path, sse=args.mock_sse)
        src = SanityContextSource(url, "mock-token")
    else:
        url, token = os.environ.get("SANITY_CONTEXT_MCP_URL"), os.environ.get("SANITY_ORGANIZATION_TOKEN")
        if not (url and token):
            sys.exit("Set SANITY_CONTEXT_MCP_URL and SANITY_ORGANIZATION_TOKEN in the environment.")
        src = SanityContextSource(url, token)

    subject = qs[0]["query"]["subject"]  # every question in one expected_answers.json shares one subject
    assert all(it["query"]["subject"] == subject for it in qs), "mixed subjects in one file -- unexpected"
    all_claims, _ = src.fetch_all(subject)
    index = BM25(build_documents(all_claims))  # one fit over this subject's whole corpus, reused per question

    systems = {"resolver": resolve, "B_newest": baseline_b, "B+scope": baseline_b_scope}
    results = {name: [answer(src, fn, it["query"]) for it in qs] for name, fn in systems.items()}
    results["A_retrieval"] = [baseline_a(all_claims, index, it["query"]) for it in qs]
    systems["A_retrieval"] = None  # already computed above; keeps iteration order for the tables below

    n = len(head)
    clusters = len({qs[i].get("cluster", i) for i in head})
    print(f"source={args.source}  set={data['meta']['set']} (held_out={data['meta']['held_out']})  "
          f"headline questions={n} in {clusters} clusters  tier-2 questions={len(tier2)}")
    for name in systems:
        res = [results[name][i] for i in head]
        its = [qs[i] for i in head]
        ok = [is_correct(it["expected"], r) for it, r in zip(its, res)]
        not_conf = [r for it, r in zip(its, res) if it["expected"]["status"] != "conflicting"]
        conf = [r for it, r in zip(its, res) if it["expected"]["status"] == "conflicting"]
        wrong_committed = sum(r["status"] in COMMITTED and not c for r, c in zip(res, ok))
        print(f"\n{name}")
        print(f"  final answer correct     {rate(sum(ok), n)}")
        print(f"  confident wrong answer   {rate(wrong_committed, n)}")
        print(f"  false conflict rate      {rate(sum(r['status'] == 'conflicting' for r in not_conf), len(not_conf))}")
        print(f"  missed conflict rate     {rate(sum(r['status'] != 'conflicting' for r in conf), len(conf))}")
        print(f"  unresolved={sum(r['status'] == 'unresolved' for r in res)}  "
              f"unsupported_case={sum(r['status'] == 'unsupported_case' for r in res)}")
        if name == "A_retrieval":
            hit = sum(1 for it, r in zip(its, res) if r.get("hit_attribute") == it["query"]["attribute"])
            print(f"  cluster hit rate (retrieval only) {rate(hit, n)}")

    def table(title, keyfn, keys):
        print(f"\n{title}")
        print(f"  {'':<34}{'n':>4}" + "".join(f"{s:>14}" for s in systems))
        for k in keys:
            idx = [i for i in head if keyfn(qs[i]) == k]
            cells = "".join(f"{sum(is_correct(qs[i]['expected'], results[s][i]) for i in idx):>14}" for s in systems)
            print(f"  {k:<34}{len(idx):>4}{cells}")

    table("correct by ground-truth status", lambda it: it["expected"]["status"],
          ["supported", "superseded", "contextual", "conflicting", "insufficient"])
    if all("template" in qs[i] for i in head):
        table("correct by template", lambda it: it["template"], sorted({qs[i]["template"] for i in head}))
    if tier2:
        got = sum(results["resolver"][i]["status"] == "unsupported_case" for i in tier2)
        print(f"\ntier-2 (deliberately unsupported): resolver reported unsupported_case {got}/{len(tier2)}")

    if args.source != "local":
        local = LocalSource(claims_path)
        same = sum(answer(local, resolve, it["query"]) == r for it, r in zip(qs, results["resolver"]))
        print(f"\nparity with local run (resolver): {same}/{len(qs)} identical")
        print(f"total MCP calls={src.calls}  time={src.seconds:.2f}s")
    if server:
        server.shutdown()


if __name__ == "__main__":
    main()
