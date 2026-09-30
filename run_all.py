#!/usr/bin/env python3
"""One-click check for PyCharm: right-click > Run 'run_all'. Standard library only.

Regenerates the fixtures, then runs the evaluator and the local and mock comparisons.
Add --live to also run against your real Sanity Context endpoint (needs
SANITY_CONTEXT_MCP_URL and SANITY_ORGANIZATION_TOKEN in the run configuration's
environment variables, never in a file that goes to GitHub).
"""
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent

STEPS = [
    ("Generate fixtures + integrity checks", ["build_fixtures.py"]),
    ("Resolver vs hand-labeled expected answers", ["evaluate.py"]),
    ("Resolver + baselines, local claims", ["compare.py", "--source", "local"]),
    ("Same, through the offline mock MCP server (JSON)", ["compare.py", "--source", "mock"]),
    ("Same, mock server replying as an event stream (SSE)", ["compare.py", "--source", "mock", "--mock-sse"]),
]
if "--live" in sys.argv:
    if not (os.environ.get("SANITY_CONTEXT_MCP_URL") and os.environ.get("SANITY_ORGANIZATION_TOKEN")):
        sys.exit("--live needs SANITY_CONTEXT_MCP_URL and SANITY_ORGANIZATION_TOKEN set in the run configuration.")
    STEPS.append(("Same, through the LIVE Sanity Context endpoint", ["compare.py", "--source", "live"]))

failed = []
for title, args in STEPS:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}", flush=True)
    code = subprocess.run([sys.executable, *args], cwd=HERE).returncode
    if code:
        failed.append(title)

print("\n" + ("ALL STEPS PASSED" if not failed else "FAILED: " + "; ".join(failed)))
sys.exit(1 if failed else 0)
