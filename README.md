# Claim Relationship Resolver

A deterministic, pure-Python agent (standard library only, no LLM API) that decides whether
retrieved claims actually conflict, built for the [Sanity Challenge, Path One](https://dev.to/challenges/sanity-2026-09-16).

Two claims can look different without disagreeing. They can also look similar while genuinely
conflicting. My resolver classifies every question into one of five outcomes — **SUPPORTED**,
**CONTEXTUAL**, **SUPERSEDED**, **CONFLICTING**, or **INSUFFICIENT** — using frozen, pre-registered
rules, no "newest wins" heuristics, and no LLM anywhere in the loop.

**Core idea: "newer" is metadata; "supersedes" is a relationship.** They're not interchangeable —
see [`RESOLVER_RULES.md`](RESOLVER_RULES.md) for the rules that make that precise.

## Results

Live, on a 404-question held-out benchmark (380 headline questions, blind-audited before I ever
looked at the generated answers):

| System | Correct | Confidently wrong | Missed conflicts |
|---|---:|---:|---:|
| **Resolver** | **380/380** | **0/380** | **0/50** |
| B+scope (recency + scope) | 276/380 | 38/380 | 50/50 |
| B_newest (recency only) | 176/380 | 180/380 | 50/50 |
| A_retrieval (BM25 keyword search) | 125/380 | 255/380 | 50/50 |

Full breakdown, methodology, and the amendments log (including two real bugs I found and fixed
during live testing) are in [`RESOLVER_RULES.md`](RESOLVER_RULES.md).

## Why GROQ mode, not a Knowledge Base

Sanity Context offers two modes: **Knowledge Bases**, which distill prose into a navigable index,
and **Context MCP with a dataset source**, queried directly with GROQ. I used the latter.

Knowledge Bases are currently capped at 150 documents in beta. My held-out benchmark alone has
456 claims — well past that budget — and the whole point of this project is reasoning over typed
fields (`scope`, `version`, `effectiveFrom`, `supersedes`), not distilled prose. A Knowledge Base
entry would flatten exactly the structure the resolver depends on.

The challenge explicitly allows this path: *"point your agent at your full dataset through a
Context MCP endpoint with embeddings enabled — both count for Path One."* I used a Context MCP
endpoint with a dataset source and queried it with the `groq_query` tool directly (no embeddings),
since retrieval here needs exact matches on `subject`/`attribute` followed by deterministic
relationship logic, not semantic similarity.

## Project structure

```
claim-relationship-resolver/
├── README.md                    — this file
├── RESOLVER_RULES.md            — frozen rules + amendments log (pre-registered)
├── LICENSE                      — MIT
├── .gitignore
├── demo.html                    — static, no-server demo page — self-contained, open directly in any browser
│
├── resolver.py                  — the frozen relationship resolver (System C)
├── baselines.py                 — Baseline A (retrieval), B (newest), B+scope
├── bm25.py                      — stdlib Okapi BM25, used by Baseline A
├── corpus.py                    — renders claims as prose documents for BM25
├── question_text.py             — deterministic natural-language question phrasing
│
├── mcp_client.py                — Sanity Context MCP client (GROQ mode, stdlib)
├── mock_mcp_server.py           — offline mock of the MCP endpoint
│
├── build_fixtures.py            — writes claims.ndjson + expected_answers.json (18 dev fixtures)
├── claims.ndjson                — dev: 5 scopes + 18 claims (subject "platform")
├── expected_answers.json        — dev: 18 hand-labeled questions
│
├── build_heldout.py             — seeded held-out generator (truth fixed by construction)
├── audit_check.py               — checks blind hand-labels against held-out truth
├── heldout/
│   ├── claims.ndjson              — 8 scopes + 456 claims (subject "heldout")
│   ├── expected_answers.json      — 404 questions (380 headline + 24 tier-2)
│   └── audit_sample.md            — 36-question blind sheet I hand-labeled
│
├── real_content/                — real data, no synthetic benchmark cases
│   ├── build_real_content.py      — builds claims from real, cited sources
│   ├── run_demo.py                — runs the resolver + baselines on real data
│   ├── claims.ndjson               — 36 real TDS articles + 20 real blog pages
│   └── README.md                   — sourcing, honesty scope, known limitations
│
├── evaluate.py                  — layered scoring vs. expected answers
├── compare.py                   — resolver + all 3 baselines, any source (local/mock/live)
├── run_all.py                   — one-click regression
│
└── schema/                      — Sanity schema, deployed with `sanity schema deploy`
    ├── scope.ts                   — hierarchical scope type
    ├── claim.ts                   — claim type, with `supersedes` relationship
    └── index.ts                   — exports schemaTypes
```

## Try it with no setup

Open `demo.html` directly in any browser (double-click it — no server, no install, no
credentials). It shows real output from this resolver, run against my own real data, next to
what three baseline systems answer for the same questions.

## Running it

Standard library only — nothing to `pip install`. Python 3.9+ (developed on 3.12).

```
python run_all.py                          # full regression: fixtures + evaluator + local/mock
python compare.py --source local           # resolver + baselines, no network
python compare.py --source mock            # same, through an offline mock MCP endpoint
python compare.py --source live --dir heldout   # against the real Sanity Context endpoint
```

`--source local` and `--source mock` reproduce identical results with **zero Sanity credentials**
needed, so the benchmark is checkable without any setup. For `--source live`, set
`SANITY_CONTEXT_MCP_URL` and `SANITY_ORGANIZATION_TOKEN` as environment variables first.

For the held-out benchmark and real-content demo specifically:

```
python build_heldout.py && python evaluate.py --dir heldout
python real_content/build_real_content.py && python real_content/run_demo.py
```

## Status and honesty notes

- `claims.ndjson`/`expected_answers.json` (top level) are **development fixtures**, not the
  held-out set — I report "reproduced all 18 hand-labeled fixtures," not "100% accuracy."
- The held-out set's truth is fixed by how each test template is constructed, never by running
  my own resolver. I hand-labeled a blind 36-question sample against the frozen rules before
  looking at the generated answers: 36/36 agreement.
- `real_content/` uses only real, cited data (my own TDS submission history and blog sitemap) and
  deliberately contains no SUPERSEDED/CONFLICTING cases, since the real snapshots I had access to
  don't contain any — see `real_content/README.md` for exactly what is and isn't demonstrated
  there.
- `RESOLVER_RULES.md`'s amendments log documents two real bugs found during live Sanity testing
  and how each was fixed, rather than smoothing them out of the record.

## Sanity Project for Submission

* Project Name: `Claim Relationship Resolver`
* Project ID: `ouvupih6`
* Dataset: `production`
* Organization ID: `o4oimb7tz`
* Dataset URL: `https://ouvupih6.apicdn.sanity.io/v2024-01-01/data/query/production?query=*[_type=="claim"]`
* Studio URL: `https://claim-relationship-resolver-emitechlogic.sanity.studio/`

Required by challenge template — include this ID in your DEV post.

## License

MIT License

Copyright (c) 2026 Emmimal P. Alexander

Permission is hereby granted, free of charge, to any person obtaining a copy...
