#!/usr/bin/env python3
"""Minimal Okapi BM25 over a small in-memory corpus. Standard library only."""
import math
import re

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return _TOKEN.findall(text.lower())


class BM25:
    """Fit on a list of {"id": ..., "tokens": [...]} docs; score(query_tokens) ranks all of them."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.N = len(docs)
        self.avgdl = sum(len(d["tokens"]) for d in docs) / self.N if self.N else 0.0
        self.df = {}
        for d in docs:
            for t in set(d["tokens"]):
                self.df[t] = self.df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in self.df.items()}

    def score(self, query_tokens):
        """Returns [(doc_id, score), ...] sorted by score desc, then doc_id asc (deterministic ties)."""
        out = []
        for d in self.docs:
            tf = {}
            for t in d["tokens"]:
                tf[t] = tf.get(t, 0) + 1
            dl = len(d["tokens"])
            s = 0.0
            for t in query_tokens:
                if t not in tf:
                    continue
                num = tf[t] * (self.k1 + 1)
                den = tf[t] + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                s += self.idf.get(t, 0.0) * num / den
            out.append((d["id"], s))
        out.sort(key=lambda p: (-p[1], p[0]))
        return out
