#!/usr/bin/env python3
"""Runs demo questions against real_content/claims.ndjson: real TDS portfolio status (subject
tds_portfolio) and a real blog-sitemap subset (subject emitechlogic_blog). Each subject gets its
own BM25 corpus for Baseline A -- mixing them would silently pollute retrieval (the same bug
found and fixed in compare.py's ALL_CLAIMS_QUERY: an unscoped corpus fetch pulls in whatever else
shares the dataset/file). Usage: python real_content/run_demo.py [--source local|mock|live]
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from baselines import baseline_a, baseline_b, baseline_b_scope
from bm25 import BM25
from build_real_content import ARTICLES, BLOG_PAGES, BLOG_SUBJECT, SUBJECT, slug
from corpus import build_documents
from mcp_client import SanityContextSource
from mock_mcp_server import start_mock
from resolver import load_local, resolve

HERE = pathlib.Path(__file__).parent
ASOF = "2026-09-24"
STAGE_NAME = {0: "draft", 1: "submitted", 2: "published"}

DEMO_SCOPES = [slug(t) for t, *_ in ARTICLES[:3]] + [slug(ARTICLES[15][0]), "all"]
BLOG_DEMO_SCOPES = [f"blog_{BLOG_PAGES[0][0]}"[:60], f"blog_{BLOG_PAGES[6][0]}"[:60], "all"]


def fmt(label, attr, r):
    if r["status"] in ("supported", "superseded", "answer"):
        v = r["answers"][0]["value"]
        return f"{label:<10} {STAGE_NAME.get(v, v) if attr == 'status_stage' else v}"
    if r["status"] == "contextual":
        return f"{label:<10} CONTEXTUAL across {len(r['answers'])} scopes (too many to list here)"
    return f"{label:<10} {r['status']}"


def run_section(title, subject, attr, scopes, fetch_q, all_claims_by_subject):
    all_claims = all_claims_by_subject(subject)
    index = BM25(build_documents(all_claims))  # THIS subject's corpus only
    print(f"--- {title} ---\n")
    for scope in scopes:
        q = {"subject": subject, "attribute": attr, "scope": scope, "asOf": ASOF}
        claims, parent = fetch_q(q)
        label = "portfolio/blog-wide" if scope == "all" else scope[:40]
        print(f"[{attr}] scope={label}")
        print(" ", fmt("resolver", attr, resolve(claims, parent, q)))
        print(" ", fmt("B_newest", attr, baseline_b(claims, parent, q)))
        print(" ", fmt("B+scope", attr, baseline_b_scope(claims, parent, q)))
        print(" ", fmt("A_retrieval", attr, baseline_a(all_claims, index, q)))
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["local", "mock", "live"], default="local")
    args = ap.parse_args()
    path = HERE / "claims.ndjson"

    server = None
    if args.source == "local":
        claims, parent = load_local(path)
        fetch_q = lambda q: (claims, parent)
        all_claims_by_subject = lambda subj: [c for c in claims if c["subject"] == subj]
    else:
        import os
        if args.source == "mock":
            server, url = start_mock(path)
            src = SanityContextSource(url, "mock-token")
        else:
            url, token = os.environ.get("SANITY_CONTEXT_MCP_URL"), os.environ.get("SANITY_ORGANIZATION_TOKEN")
            if not (url and token):
                sys.exit("Set SANITY_CONTEXT_MCP_URL and SANITY_ORGANIZATION_TOKEN in the environment.")
            src = SanityContextSource(url, token)
        fetch_q = src.fetch
        all_claims_by_subject = lambda subj: src.fetch_all(subj)[0]

    print(f"source={args.source}  real content as of 2026-09-23/24\n")
    run_section("real TDS portfolio status (36 articles)", SUBJECT, "status_stage",
                DEMO_SCOPES, fetch_q, all_claims_by_subject)
    run_section("real TDS portfolio: editor assignment", SUBJECT, "editor_assigned",
                DEMO_SCOPES, fetch_q, all_claims_by_subject)
    run_section("real EmiTechLogic blog sitemap (top 20 by recency)", BLOG_SUBJECT, "image_count",
                BLOG_DEMO_SCOPES, fetch_q, all_claims_by_subject)

    if server:
        server.shutdown()


if __name__ == "__main__":
    main()
