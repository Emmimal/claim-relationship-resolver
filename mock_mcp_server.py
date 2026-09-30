#!/usr/bin/env python3
"""Offline mock of a Sanity Context MCP endpoint (GROQ mode). Standard library only.

It is NOT a GROQ engine. It answers exactly the three query shapes mcp_client.py builds
(claims by subject+attribute, all scopes, and the subject-scoped all-claims query used by
Baseline A) and rejects every other query.
Run standalone:  python mock_mcp_server.py [--sse]
"""
import json
import pathlib
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mcp_client import SCOPES_QUERY, all_claims_query, claims_query
from resolver import load_local

_SHAPE = re.compile(r'^\*\[_type=="claim" && subject=="([A-Za-z0-9_]+)" && attribute=="([A-Za-z0-9_]+)"\]')
HERE = pathlib.Path(__file__).parent


def make_server(claims_path, sse=False, port=0):
    claims, parent = load_local(claims_path)

    def _row(c):
        row = {k: c[k] for k in ("id", "subject", "attribute", "value", "scope", "version", "effectiveFrom")}
        row["supersedes"] = c["supersedes"] or None  # GROQ gives null for a missing array
        return row

    subjects = {c["subject"] for c in claims}

    def run_query(query):
        if query == SCOPES_QUERY:
            return [{"scopeId": s, "parent": p} for s, p in sorted(parent.items())]
        for subj in subjects:
            if query == all_claims_query(subj):
                return [_row(c) for c in claims if c["subject"] == subj]
        m = _SHAPE.match(query)
        if m and query == claims_query(*m.groups()):
            return [_row(c) for c in claims if (c["subject"], c["attribute"]) == m.groups()]
        raise ValueError("mock supports only the three query shapes built by mcp_client.py")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, obj):
            body, ctype = json.dumps(obj).encode("utf-8"), "application/json"
            if sse and status == 200:
                body, ctype = b"event: message\ndata: " + body + b"\n\n", "text/event-stream"
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self.headers.get("Authorization", "").startswith("Bearer "):
                return self._send(401, {"error": "missing bearer token"})
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            rid, method = req.get("id"), req.get("method")
            if method == "tools/list":
                return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "groq_query"}]}})
            if method == "tools/call" and req["params"]["name"] == "groq_query":
                query = req["params"]["arguments"]["query"]
                try:
                    rows = run_query(query)
                except ValueError as e:
                    return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {
                        "isError": True, "content": [{"type": "text", "text": str(e)}]}})
                payload = {"meta": {"executedQuery": query, "perspective": "published",
                                    "resultCount": len(rows), "returnedCount": len(rows)}, "result": rows}
                return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": json.dumps(payload)}]}})
            self._send(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def start_mock(claims_path, sse=False):
    server = make_server(claims_path, sse)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1/context/organizations/mock/mcp/dev"


if __name__ == "__main__":
    srv = make_server(HERE / "claims.ndjson", sse="--sse" in sys.argv, port=8787)
    print("mock MCP on http://127.0.0.1:8787/  (Ctrl+C to stop)")
    srv.serve_forever()
