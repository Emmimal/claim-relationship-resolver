# Real-content demo

**Two real, independent datasets, two subjects in the same file:**

1. **`tds_portfolio`** -- my TDS Contributor Portal article listing as of 2026-09-23: 36 real
   articles, real status (Draft/Submitted/Published), real editor assignment, real
   submission/publish dates. See `ARTICLES` in `build_real_content.py`.
2. **`emitechlogic_blog`** -- my EmiTechLogic sitemap as of 2026-09-24. A deliberate **subset**:
   the top 20 of roughly 200 listed pages, by most-recently-updated, chosen to avoid
   transcription risk across the full list rather than because the rest was unavailable. Real
   image count and real Last Updated date per page. See `BLOG_PAGES`.

Nothing in `claims.ndjson` is invented, estimated, or inferred beyond those two real listings.

**Subjects are kept strictly separate.** `run_demo.py` builds one BM25 corpus per subject for
Baseline A -- the same bug found and fixed in `compare.py`'s `ALL_CLAIMS_QUERY` (an unscoped
corpus silently absorbs whatever else shares the dataset/file) turned up again here before I ran
it live, and got the same fix.

**Two claims per article:** `status_stage` (0=draft, 1=submitted, 2=published -- an ordinal
encoding of the real status column, translated back to the label in `run_demo.py`) and
`editor_assigned` (0/1, from the real "No editor assigned" / "Editor: Ben Huberman" column).
Scope = one real article per leaf, under a shared `all`.

**Honesty scope -- what this demo can and cannot show.** This is a single real snapshot: each
article has exactly one recorded state, not a history. It genuinely and honestly demonstrates:
- **SUPPORTED**: a real, specific article's real current status/editor.
- **CONTEXTUAL**: asking about the whole portfolio (scope `all`) correctly returns a per-article
  breakdown across 34 real articles, rather than one number.
- **INSUFFICIENT**: two real Draft rows ("Multi-Agent Systems Don't Need Another Agent...",
  "Vibe Coding Ships Fast...") have no submission date in my listing. `effectiveFrom` is left
  unset for them rather than guessed -- Rule 4 (missing means unknown) -- so they correctly
  resolve as unknown rather than "current."

It does **not** demonstrate SUPERSEDED or CONFLICTING: this snapshot contains no article with two
differing recorded states, so building either into this dataset would mean inventing a change
that never happened. Those two statuses are demonstrated only by the held-out benchmark, which
is clearly and separately labeled as a synthetic, blind-audited corpus -- see `../heldout/` and
`../RESOLVER_RULES.md`. I'm not presenting this real-content section as showing supersession or
conflict resolution -- it doesn't, honestly, and I'm not making it look like it does.

**What it does show clearly: scope-blindness fails on real data too.** Baseline B (newest wins,
scope-blind) answers every "what's the status of article X" question with whatever my single
most recently dated claim happens to be across my *entire* portfolio -- currently "submitted",
my most recent real submission -- regardless of which real article was asked about. Asked for the
whole portfolio, B and B+scope and A_retrieval each collapse 34 different real statuses into one
wrong single answer; only the resolver correctly says "it depends which article."

**Run it:**
```
python build_real_content.py
python run_demo.py                    # local
python run_demo.py --source mock
python run_demo.py --source live      # needs SANITY_CONTEXT_MCP_URL / SANITY_ORGANIZATION_TOKEN
```
For a live run, import first (from sanity-studio) -- uses subjects `tds_portfolio` and
`emitechlogic_blog`, coexisting alongside `platform`/`heldout` without mixing:
```
npx sanity dataset import ..\claim-relationship-resolver\real_content\claims.ndjson production --replace
```

This is a qualitative, narrated demo for my write-up/video, built from real data with disclosed
limits -- not a scored benchmark. For statistical evidence, see `compare.py --dir heldout`.
