#!/usr/bin/env python3
"""Render claims as short prose documents, the way a plain-text KB article might state them.

Deliberately omits `supersedes` and any relationship metadata: a keyword search over prose
sees isolated statements of fact, not a structured graph. That gap is the whole point of
Baseline A (retrieval-only, no relationship reasoning).
"""
from bm25 import tokenize


def render(claim):
    attr = claim["attribute"].replace("_", " ")
    scope = (claim["scope"] or "unspecified").replace("_", " ")
    bits = [f"{attr} for {scope}", f"is {claim['value']}"]
    if claim.get("version"):
        bits.append(f"in version {claim['version']}")
    if claim.get("effectiveFrom"):
        bits.append(f"effective {claim['effectiveFrom']}")
    return " ".join(bits) + "."


def build_documents(claims):
    return [{"id": c["id"], "text": render(c), "tokens": tokenize(render(c))} for c in claims]
