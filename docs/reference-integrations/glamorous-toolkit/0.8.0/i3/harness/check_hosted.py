"""GT 0.8.0 I3 drift check: hosted AIP still serves the frozen I1 answer.

Re-runs the frozen I1 `query` request against https://mcp.daip.io/mcp and compares the snapshot
id and the canonical answer digest with the I1 freeze record. Exit 2 on any difference.

    check_hosted.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GT080 = HERE.parents[1]
REPO = GT080.parents[3]
EDGE = REPO / "examples/sokol111-demo/hosted/verify_public_edge.py"
REQUEST = GT080 / "i1-freeze/aip/query.request.json"
URL = "https://mcp.daip.io/mcp"
FROZEN_SNAPSHOT = "aip:snapshot:v1:7f171aea2d3c5070e6be3dd9c6b53a234ad75934be5724681b95cd3e1705c413"
FROZEN_DIGEST = "9c97b871e1369c0c06cd14b4850110b8a1e62c59693f154bf2ede2bc08945c81"


def canonical_digest(structured: dict) -> str:
    """The I1 convention: default separators, sorted keys, one trailing newline."""
    return hashlib.sha256((json.dumps(structured, sort_keys=True) + "\n").encode()).hexdigest()


def main() -> int:
    spec = importlib.util.spec_from_file_location("verify_public_edge", EDGE)
    if spec is None or spec.loader is None:
        print(f"STOP: cannot load {EDGE}", file=sys.stderr)
        return 2
    edge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(edge)
    params = json.loads(REQUEST.read_text())["params"]
    ok, answer = edge._tool_call(URL, 1, params["name"], params["arguments"])
    if not ok or not isinstance(answer, dict):
        print(f"STOP: {answer}", file=sys.stderr)
        return 2
    snapshot = (answer.get("snapshot") or {}).get("snapshot_id")
    digest = canonical_digest(answer)
    problems = []
    if snapshot != FROZEN_SNAPSHOT:
        problems.append(f"snapshot {snapshot} is not the frozen one")
    if digest != FROZEN_DIGEST:
        problems.append(f"answer digest {digest} is not the frozen one")
    for problem in problems:
        print(f"STOP: {problem}", file=sys.stderr)
    if problems:
        return 2
    print(f"hosted AIP: frozen snapshot and answer digest {digest[:12]}… unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
