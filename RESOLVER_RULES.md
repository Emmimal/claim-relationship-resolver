# Resolver rules (pre-registered)

**Status: FROZEN for dev batch 1 (2026-09-19).** After held-out questions exist, change nothing in place: add a dated entry to the amendments log at the bottom, with the reason.

Principle: **"newer" is metadata; "supersedes" is a relationship.** They are not interchangeable.

## Rules

1. **Explicit supersession only.** A claim is stale only where an eligible claim links to it with `supersedes: {claim, inScope}`, and only within `inScope`. No newest-version heuristic, no source-authority ranking, no "official docs win". `sourceType` never affects resolution.
2. **Scope containment and conflict.** A narrower applicable scope overrides a broader applicable scope for that scope only. Among claims applicable at the same narrowest scope, different values are a conflict unless an explicit supersession relationship resolves the difference. Version or date differences alone never resolve a conflict.
3. **Temporal validity.** Every question has an `asOf` date. A claim with `effectiveFrom > asOf` is ineligible. Never infer a date from a version string.
4. **Missing metadata is unknown, never an implicit fact.** A null scope, date or version does not mean "all scopes / current / always". Unknown metadata cannot establish applicability and may yield INSUFFICIENT. A claim without a date is neither newer nor older than another.

## Operational definitions

- **Query:** (subject, attribute, scope Q, asOf). Q = `all` means "scope unspecified".
- **Eligible:** `effectiveFrom` present and <= asOf.
- **Applicable:** claim scope is Q or an ancestor of Q.
- **Stale for Q:** an eligible claim Y with a link `{X, inScope T}` makes X stale when T is Q or an ancestor of Q. A stale claim keeps its own power to supersede.
- **Live:** eligible, applicable, not stale, and at the deepest applicable scope present.

## Outcomes

| Condition | Status |
|---|---|
| No claims exist for the attribute | INSUFFICIENT (`no_claims`) |
| Claims exist, none eligible | INSUFFICIENT (`not_yet_effective`, or `unknown_metadata` if no date) |
| Eligible claims exist, none applicable, Q is a leaf | INSUFFICIENT (`no_applicable_claim`) |
| Eligible claims exist, none applicable, claims exist in descendant scopes of Q | CONTEXTUAL: one resolved answer per descendant scope |
| One distinct live value, no supersession involved | SUPPORTED |
| One distinct live value, at least one claim excluded by supersession | SUPERSEDED |
| More than one distinct live value | CONFLICTING |
| Tier-2 case (see open items) | UNSUPPORTED_CASE: the resolver raises `NotImplementedError`, the pipeline reports `unsupported_case`. Never an invented answer. |

## Baselines (pre-registered)

- **A, retrieval only:** deferred until natural-language question text exists (needs BM25 over question strings).
- **B, newest wins:** as-of eligible claims, scope-blind, newest `effectiveFrom`.
- **B+scope:** as-of eligible, scope-applicable, narrowest applicable scope, then newest `effectiveFrom`.
- **Ties are never broken.** All tied claims are returned; if their values differ the status is `unresolved` (conflict not explicitly handled), which counts as *not* detecting a conflict.
- *Interpretation note:* the design note said B should "filter to applicable claims". I read that as as-of eligibility only, so that B+scope is what adds scope.
- **Scoring (compare.py `is_correct`):** one rule for all systems. Single-valued truth: one distinct value equal to the truth. Contextual: same (scope, value) set. Conflicting: status conflicting and the same value set. Insufficient: status insufficient or none.

## Open items (tier 2, deliberately unimplemented)

1. A question scope that has both applicable claims and descendant-scope claims (for example `payload_mb` with scope `all`).
2. A contextual split where a child scope resolves to conflicting or insufficient.
3. Cross-dimension scopes (enterprise and legacy together).
4. `effectiveTo`, and "no end date" versus "unknown end date" under Rule 4.

## Amendments log

- 2026-09-19: Rule 2 reworded, dropping the "same version/date" qualifier so recency can never resolve a conflict. Baseline tie rule registered.
- 2026-09-19 (registered while writing the held-out generator, before any official run):
  - A claim with a missing scope, when it is the only claim, yields INSUFFICIENT with reason `no_applicable_claim`.
  - A supersession link whose `inScope` is missing establishes nothing (Rule 4), so the claims it names stay live.
  - Tier-2 questions carry `headline: false` and expected status `unsupported_case`; they are reported separately and excluded from the headline rates.
  - Added metric **confident wrong answer**: the system committed to an answer (supported, superseded, contextual, or a baseline "answer") and it was wrong. Flagging a conflict, abstaining (insufficient/none), `unresolved` and `unsupported_case` are not confident answers.
  - Questions inside one cluster share claims and are not independent: report the cluster count next to every interval.
- 2026-09-19: a harness smoke run of the seed-2026 held-out set was made before the blind audit (resolver 404/404 against the by-construction truth; no resolver or template change followed). Treat the blind audit as the independent check.
- 2026-09-19: Baseline A (retrieval-only) implemented. BM25 over the WHOLE claim corpus (any
  subject/attribute, not just the question's), each claim rendered as plain prose with `corpus.py`
  (value, scope, version, effectiveFrom -- deliberately never `supersedes`, since a keyword search
  over prose text has no access to a formal relationship graph). Question text is generated
  deterministically from the query's own fields by `question_text.py` (never from the expected
  answer, so it can't leak truth). Returns the single top-ranked document's value with no scope
  containment, no supersession, no conflict detection -- exactly "if a keyword search would have
  gotten you the same answer" from the challenge brief. New metric: **cluster hit rate** (did the
  top-ranked document even belong to the right attribute?), reported for A_retrieval only, since B
  and B+scope are given the correct attribute by construction (their unfairness runs the other way).
  Caveat: held-out attribute names are anonymized (`h_metric_###`), so Baseline A there tests the
  retrieval MECHANISM, not real lexical ambiguity -- the dev fixtures (real attribute names like
  `max_items`) and the real-content demo are where this baseline is actually informative.
- 2026-09-19 (bug found from the live run, fixed same day): the first `ALL_CLAIMS_QUERY` used by
  Baseline A was unfiltered by subject (`*[_type=="claim"]`). On the live "production" dataset,
  which holds BOTH the dev fixtures (subject `platform`, 18 claims) and the held-out set (subject
  `heldout`, 456 claims) side by side, this silently pulled all 474 into Baseline A's BM25 corpus,
  shifting its term statistics and dragging its score down (live: 112/380, vs. the correct local
  125/380). Fixed: `all_claims_query(subject)` and `fetch_all(subject)` are now subject-scoped,
  same as `claims_query`. Verified against a deliberately contaminated local dataset (held-out +
  dev fixtures combined, matching the live layout) that the fix excludes the other subject.
  Resolver, B_newest and B+scope were never affected (their fetch was always subject-scoped) --
  this is why the resolver's 404/404 parity held throughout even while A_retrieval's live number
  was wrong; parity was only ever checked for the resolver, not the baselines. The live A_retrieval
  number must be re-run after this fix; do not report the pre-fix 112/380.
- 2026-09-19 (second bug, found on the first live retry after the subject-scoping fix): the
  rewritten `all_claims_query` had a copy/paste brace typo (`}}}` instead of `}}`), producing
  invalid GROQ that Sanity correctly rejected ("Unexpected end of query"). The offline mock's
  matcher compares query strings verbatim rather than parsing GROQ, so it never caught this --
  a reminder that mock parity checks prove transport/normalization consistency, not query
  validity. Fixed to match `claims_query`'s brace structure exactly; verified brace-balanced
  and structurally identical (byte-for-byte after the subject filter) before re-testing.
