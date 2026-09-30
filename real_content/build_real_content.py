#!/usr/bin/env python3
"""Real-content demo, sourced ONLY from my TDS Contributor Portal listing as of 2026-09-23.
Every (title, status, editor, date) tuple below is copied directly from that listing -- nothing
here is inferred, estimated, or invented.

Honesty scope: this single snapshot shows each article's CURRENT status only. It contains no
article with two differing recorded states, so it can't honestly demonstrate SUPERSEDED or
CONFLICTING -- only SUPPORTED, CONTEXTUAL (many real articles under one query), and INSUFFICIENT
(two Draft rows have no submission/publish date in my listing and are left undated on purpose,
per Rule 4: missing means unknown, never "now"). SUPERSEDED/CONFLICT are already demonstrated,
and clearly labeled as synthetic, by the held-out benchmark -- this demo doesn't try to
recreate them with real data that doesn't contain them.

Standard library only. Writes real_content/claims.ndjson.
"""
import datetime
import json
import pathlib
import re

OUT = pathlib.Path(__file__).parent
SUBJECT = "tds_portfolio"
STAGE = {"draft": 0, "submitted": 1, "published": 2}  # ordinal encoding, see README

# (title, status, editor_assigned, date_or_None) -- copied verbatim from the pasted portal listing.
# date_or_None is the real Submitted/Published date shown next to the title; None where the
# source gave none (both Draft rows).
ARTICLES = [
    ("RAG Isn't an Agent — I Built the Layer Between Retrieval and Action", "submitted", False, "2026-09-23"),
    ("Multi-Agent Coding Isn't Enough — Agents Need a Commitment Layer", "published", True, "2026-09-18"),
    ("Coding Agents Don't Need Longer History — They Need Intent Continuity", "published", True, "2026-09-11"),
    ("Context Windows Don't Know What's Still True — I Built a Validity Layer That Does", "published", True, "2026-09-08"),
    ("Changing One Prompt Can Affect 50 Others — I Built a Prompt Dependency Graph to Find What Needs Retesting", "published", True, "2026-09-03"),
    ("AI Agents Don't Need More Context — They Need Typed Context", "published", False, "2026-08-24"),
    ("Graph Engineering Isn't About More Connections — It's About Which Ones Get Used", "published", False, "2026-08-18"),
    ("Coding Agents Don't Need Bigger Context Windows — They Need a Context Compiler", "published", False, "2026-08-01"),
    ("Prompt Engineering Is Solved—Prompt Management Isn't", "published", False, "2026-07-29"),
    ("Context Windows Forget What Matters — I Built a Usage-Reinforced Decay Engine for AI Agent Memory", "published", False, "2026-07-24"),
    ("Context Engineering Isn't Enough — A Loop Engineering Experiment With No LLM Inside the Loop", "published", False, "2026-07-17"),
    ("Long Context Isn't Free — I Built a Safe Prompt-Pruning Layer That Makes LLM Systems Work", "published", False, "2026-07-11"),
    ("LLM Wikis Are Over-Engineered — I Replaced Mine With a Pure Python Compiler", "published", False, "2026-07-03"),
    ("Prompt Engineering Fails Quietly — Prompt Regression Is Why", "published", False, "2026-06-29"),
    ("Vector RAG Isn't Enough — I Built a Context Graph Layer for Multi-Agent Memory", "published", False, "2026-06-26"),
    ("Multi-Agent Systems Don't Need Another Agent — I Replaced an LLM Router With a 1ms Classifier", "draft", False, None),
    ("LLM Fallbacks Break Agent Pipelines — I Built the Missing Recovery Layer", "published", False, "2026-06-16"),
    ("Larger Context Windows Don't Fix RAG — So I Built a System That Does", "published", False, "2026-06-13"),
    ("My AI Couldn't See My Files — I Built a Zero-Dependency MCP Server", "published", False, "2026-06-05"),
    ("Vibe Coding Ships Fast—and Ships Vulnerabilities. I Built a Scanner for AI Blind Spots", "draft", False, None),
    ("RAG Is Burning Money — I Built a Cost Control Layer to Fix It", "published", False, "2026-05-29"),
    ("Prompt Engineering Isn't Enough — I Built a Control Layer That Works in Production", "published", False, "2026-05-21"),
    ("LLM Evals Are Based on Vibes — I Built the Missing Layer That Decides What Ships", "published", False, "2026-05-17"),
    ("RAG Is Blind to Time — I Built a Temporal Layer to Fix It in Production", "published", False, "2026-05-09"),
    ("RAG Hallucinates — I Built a Self-Healing Layer That Fixes It in Real Time", "published", False, "2026-05-05"),
    ("PyTorch NaNs Are Silent Killers — So I Built a 3ms Hook to Catch Them at the Exact Layer", "published", False, "2026-04-28"),
    ("Your RAG Gets Confidently Wrong as Memory Grows – I Built the Memory Layer That Stops It", "published", False, "2026-04-21"),
    ("Your RAG System Retrieves the Right Data — But Still Produces Wrong Answers. Here's Why (and How to Fix It).", "published", False, "2026-04-18"),
    ("RAG Isn't Enough — I Built the Missing Context Layer That Makes LLM Systems Work", "published", False, "2026-04-14"),
    ("Your ReAct Agent Is Wasting 90% of Its Retries — Here's How to Stop It", "published", False, "2026-04-12"),
    ("Why MLOps Retraining Schedules Fail — Models Don't Forget, They Get Shocked", "published", False, "2026-04-10"),
    ("Explainable AI in Production: A Neuro-Symbolic Model for Real-Time Fraud Detection", "published", False, "2026-03-30"),
    ("Self-Healing Neural Networks in PyTorch: Fix Model Drift in Real Time Without Retraining", "published", False, "2026-03-29"),
    ("Neuro-Symbolic Fraud Detection: Catching Concept Drift Before F1 Drops (Label-Free)", "published", False, "2026-03-23"),
    ("How a Neural Network Learned Its Own Fraud Rules: A Neuro-Symbolic AI Experiment", "published", False, "2026-03-17"),
    ("Hybrid Neuro-Symbolic Fraud Detection: Guiding Neural Networks with Domain Rules", "published", False, "2026-03-10"),
]


def slug(title):
    s = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return s[:60]


def R(_id):
    return {"_type": "reference", "_ref": _id}


def build():
    seen, scopes, claims = set(), [{"_id": "scope-all", "_type": "scope", "scopeId": "all"}], []
    for i, (title, status, has_editor, date) in enumerate(ARTICLES, start=1):
        sid = slug(title)
        if sid in seen:
            sid = f"{sid}_{i}"
        seen.add(sid)
        scopes.append({"_id": f"scope-{sid}", "_type": "scope", "scopeId": sid,
                       "parent": R("scope-all")})
        base = {"_type": "claim", "subject": SUBJECT, "scope": R(f"scope-{sid}"),
                "version": "portal-2026-09-23", "sourceId": "tds-contributor-portal",
                "sourceType": "internal_portal_listing"}
        if date:
            base["effectiveFrom"] = date
        c1 = {**base, "_id": f"claim-status{i:03d}", "claimId": f"status{i:03d}",
              "attribute": "status_stage", "value": STAGE[status], "unit": "stage"}
        c2 = {**base, "_id": f"claim-editor{i:03d}", "claimId": f"editor{i:03d}",
              "attribute": "editor_assigned", "value": 1 if has_editor else 0, "unit": "boolean"}
        claims += [c1, c2]
    return scopes + claims


def check(docs):
    ids = {d["_id"] for d in docs}
    assert len(ids) == len(docs), "duplicate _id"
    for d in docs:
        if "effectiveFrom" in d:
            datetime.date.fromisoformat(d["effectiveFrom"])
        for key in ("scope", "parent"):
            if key in d:
                assert d[key]["_ref"] in ids
    n_claims = sum(1 for d in docs if d["_type"] == "claim")
    assert n_claims == len(ARTICLES) * 2 + len(BLOG_PAGES)


# -- Second real dataset: EmiTechLogic blog sitemap, top 20 most-recently-updated pages of the
# ~200 in my sitemap as of 2026-09-24. A deliberate subset, chosen to avoid transcription risk
# across the full sitemap rather than any gap in the source -- these are the top 20 rows of that
# listing, verbatim (URL slug, real image count, real Last Updated date).
BLOG_SUBJECT = "emitechlogic_blog"
BLOG_PAGES = [
    ("blog", 7, "2026-02-13"),
    ("how-to-analyze-the-time-and-space-complexity-of-an-algorithm", 7, "2026-09-18"),
    ("recursion-in-python-how-recursive-algorithms-actually-work", 5, "2026-09-16"),
    ("best-average-worst-case-time-complexity", 6, "2026-09-16"),
    ("data-structures-and-algorithms-python", 4, "2026-09-16"),
    ("big-o-notation-in-python", 6, "2026-09-11"),
    ("ml-technical-debt-how-to-identify-measure-and-pay-it-down", 4, "2026-08-28"),
    ("machine-learning-production-pipeline", 9, "2026-08-28"),
    ("ml-production-readiness-checklist-50-things-to-verify-before-you-ship", 4, "2026-08-28"),
    ("how-to-a-b-test-machine-learning-models-the-right-way", 5, "2026-08-21"),
    ("debug-ml-inference-latency", 4, "2026-07-23"),
    ("shadow-deployment-and-canary-testing-for-machine-learning-models-a-practical-guide", 5, "2026-07-14"),
    ("ml-model-monitoring-how-to-detect-data-drift-and-model-decay-in-production", 4, "2026-07-02"),
    ("how-to-build-an-ml-monitoring-dashboard-from-scratch-streamlit-tutorial", 2, "2026-07-02"),
    ("how-to-prevent-catastrophic-forgetting-in-pytorch", 5, "2026-06-04"),
    ("online-learning-machine-learning-python", 4, "2026-06-04"),
    ("continual-learning-in-pytorch", 4, "2026-06-04"),
    ("retrain-vs-fine-tune-vs-train-from-scratch-a-decision-framework-for-ml-engineers", 4, "2026-06-04"),
    ("model-versioning-in-production-machine-learning", 5, "2026-05-20"),
    ("how-to-build-an-ml-retraining-pipeline-that-wont-break-in-production", 5, "2026-05-20"),
]


def build_blog():
    scopes, claims = [], []
    for i, (page_slug, images, date) in enumerate(BLOG_PAGES, start=1):
        sid = f"blog_{page_slug}"[:60]
        scopes.append({"_id": f"scope-{sid}", "_type": "scope", "scopeId": sid, "parent": R("scope-all")})
        claims.append({"_id": f"claim-blog{i:03d}", "_type": "claim", "claimId": f"blog{i:03d}",
                        "subject": BLOG_SUBJECT, "attribute": "image_count", "value": images,
                        "unit": "images", "scope": R(f"scope-{sid}"), "version": "sitemap-2026-09-24",
                        "effectiveFrom": date, "sourceId": "emitechlogic-sitemap",
                        "sourceType": "internal_sitemap_listing"})
    return scopes, claims


def main():
    docs = build()
    blog_scopes, blog_claims = build_blog()
    docs += blog_scopes + blog_claims
    check(docs)
    with open(OUT / "claims.ndjson", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    n_scope = sum(1 for d in docs if d["_type"] == "scope")
    n_claim = sum(1 for d in docs if d["_type"] == "claim")
    undated = sum(1 for a in ARTICLES if a[3] is None)
    print(f"{len(docs)} documents ({n_scope} scopes, {n_claim} claims) -> real_content/claims.ndjson")
    print(f"  {len(ARTICLES)} real TDS articles (subject={SUBJECT}), {undated} left undated on purpose")
    print(f"  {len(BLOG_PAGES)} real blog pages, top-20-by-recency subset (subject={BLOG_SUBJECT})")
    print("Sources: TDS Contributor Portal listing (2026-09-23) and EmiTechLogic sitemap "
          "(2026-09-24), both pasted into chat. Contains no SUPERSEDED/CONFLICT cases -- see README.md.")


if __name__ == "__main__":
    main()
