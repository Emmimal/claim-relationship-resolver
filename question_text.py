#!/usr/bin/env python3
"""Deterministic natural-language phrasing for a query dict. Standard library only.

Generated straight from the query's own fields (subject/attribute/scope/asOf), never from the
expected answer, so it can't leak ground truth. Attribute ids in the held-out set are anonymized
(h_metric_###), so this exercises the retrieval MECHANISM, not real-world lexical ambiguity;
the dev fixtures and the real-content demo use meaningful attribute names, which is where this
baseline is actually informative.
"""
import zlib

from bm25 import tokenize

VARIANTS = [
    "What is {attr}{scope}?",
    "What's the current value of {attr}{scope}?",
    "How much is {attr}{scope} as of {asof}?",
    "What is the limit for {attr}{scope}?",
    "Can you tell me {attr}{scope}?",
]


def phrase(q):
    attr = q["attribute"].replace("_", " ")
    scope = "" if not q["scope"] or q["scope"] == "all" else f" for {q['scope'].replace('_', ' ')}"
    key = f"{q['subject']}|{q['attribute']}|{q['scope']}|{q['asOf']}"
    variant = VARIANTS[zlib.crc32(key.encode()) % len(VARIANTS)]
    return variant.format(attr=attr, scope=scope, asof=q["asOf"])


def question_tokens(q):
    return tokenize(phrase(q))
