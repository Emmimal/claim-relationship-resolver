#!/usr/bin/env python3
"""Minimal Sanity Context MCP client (GROQ mode). Standard library only.

Follows Sanity's documented curl example: stateless JSON-RPC POSTs to
https://api.sanity.io/v1/context/organizations/<orgId>/mcp/<endpointName>.
The bearer token must be an ORGANIZATION API token with Context Viewer
(a project token is refused with 403 contextGrantRequired).

NOT yet run against a live endpoint. mock_mcp_server.py implements the same shapes.
"""
import json
import re
import time
import urllib.error
import urllib.request

_IDENT = re.compile(r"^[A-Za-z0-9_]+$")
SCOPES_QUERY = '*[_type=="scope"]{scopeId, "parent":parent->scopeId}'
def all_claims_query(subject):
    """Every claim for one subject, any attribute. Used ONLY by Baseline A, which must search
    the whole corpus for a deployment the way a plain keyword search would -- not narrowed to
    the question's own attribute (that would be structured filtering, exactly what this
    baseline is meant to go without). Still scoped to `subject`: a live Sanity dataset can hold
    more than one experiment's documents side by side (e.g. dev fixtures and held-out both live
    in the same "production" dataset here), and an unscoped query would silently mix them into
    one corpus -- a benchmark artifact, not something a real single-KB deployment would ever face.
    """
    if not _IDENT.match(subject):
        raise ValueError(f"unsafe identifier: {subject!r}")
    return (
        f'*[_type=="claim" && subject=="{subject}"]'
        '{"id":_id, subject, attribute, value, "scope":scope->scopeId, version, effectiveFrom, '
        '"supersedes":supersedes[]{"claim":claim._ref, "inScope":inScope->scopeId}}'
    )


def claims_query(subject, attribute):
    """groq_query takes only a query string (no $params), so values are inlined
    after validating them as plain identifiers."""
    for v in (subject, attribute):
        if not _IDENT.match(v):
            raise ValueError(f"unsafe identifier: {v!r}")
    return (
        f'*[_type=="claim" && subject=="{subject}" && attribute=="{attribute}"]'
        '{"id":_id, subject, attribute, value, "scope":scope->scopeId, version, effectiveFrom, '
        '"supersedes":supersedes[]{"claim":claim._ref, "inScope":inScope->scopeId}}'
    )


def parse_response(body, content_type):
    """The endpoint may answer with plain JSON or a server-sent-event stream."""
    text = body.decode("utf-8")
    if "text/event-stream" in content_type:
        msgs = [json.loads(line[5:].strip()) for line in text.splitlines()
                if line.startswith("data:") and line[5:].strip()]
        msgs = [m for m in msgs if "result" in m or "error" in m]
        if not msgs:
            raise RuntimeError("event stream carried no JSON-RPC response")
        return msgs[-1]
    return json.loads(text)


def _claim(row):
    # GROQ returns null (not []) for a missing array, so normalize it.
    return {
        "id": row["id"], "subject": row.get("subject"), "attribute": row.get("attribute"),
        "value": row.get("value"), "scope": row.get("scope"), "version": row.get("version"),
        "effectiveFrom": row.get("effectiveFrom"),
        "supersedes": [{"claim": s.get("claim"), "inScope": s.get("inScope")}
                       for s in (row.get("supersedes") or [])],
    }


class SanityContextSource:
    """fetch(q) -> (claims, scope_parent), the exact input the resolver takes."""

    def __init__(self, url, token, timeout=30):
        self.url, self.token, self.timeout = url, token, timeout
        self.calls, self.seconds = 0, 0.0
        self._parent, self._id = None, 0
        self._cache = {}

    def _rpc(self, method, params=None):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Authorization": f"Bearer {self.token}",
                     "Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                msg = parse_response(r.read(), r.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}") from e
        finally:
            self.calls += 1
            self.seconds += time.perf_counter() - t0
        if "error" in msg:
            raise RuntimeError(f"JSON-RPC error: {msg['error']}")
        return msg["result"]

    def groq(self, query):
        res = self._rpc("tools/call", {"name": "groq_query", "arguments": {"query": query}})
        payload = res.get("structuredContent")
        if payload is None:
            text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
            if res.get("isError"):
                raise RuntimeError(f"groq_query error: {text[:300]}")
            payload = json.loads(text)
        meta = payload.get("meta", {})
        if meta.get("warnings") or meta.get("resultCount") != meta.get("returnedCount"):
            raise RuntimeError(f"result cropped or truncated: {meta}")
        return payload["result"]

    def fetch(self, q):
        key = (q["subject"], q["attribute"])
        if key not in self._cache:  # one MCP call per (subject, attribute), however many questions use it
            self._cache[key] = [_claim(r) for r in self.groq(claims_query(*key))]
        if self._parent is None:
            self._parent = {r["scopeId"]: r.get("parent") for r in self.groq(SCOPES_QUERY)}
        return self._cache[key], self._parent

    def fetch_all(self, subject):
        """All claims for one subject (any attribute). One call, cached for this source's lifetime."""
        key = ("*", subject)
        if key not in self._cache:
            self._cache[key] = [_claim(r) for r in self.groq(all_claims_query(subject))]
        if self._parent is None:
            self._parent = {r["scopeId"]: r.get("parent") for r in self.groq(SCOPES_QUERY)}
        return self._cache[key], self._parent
