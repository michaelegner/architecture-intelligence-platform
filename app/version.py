"""v0.4.1 I3.2 - the one place AIP's own package/producer version is read from.

PR #120 review finding: `app/mcp/server.py`, `app/mcp/wiring.py`, and
`evaluation/architecture_answers/runner.py`'s synthetic evaluation producer each independently
hardcoded their own version literal - which is exactly how the evaluator's `_build_producer` was
still constructing a `0.4.0` producer (and its 23 frozen `expected_answer.json` fixtures still
expected `0.4.0`) even after `pyproject.toml`/the production MCP wiring had already moved to
`0.4.1`. `pyproject.toml` is the single source of truth; every other call site SHALL import
`package_version()` from here rather than maintaining its own literal, so they cannot independently
drift again.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"


def package_version() -> str:
    with _PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]
