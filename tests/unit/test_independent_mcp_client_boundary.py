"""v0.4.0 I2.4 - spec §17 scenario 22 ("The client imports no AIP internal module"). Static/AST-level
rather than behavioral, mirroring `tests/unit/test_mcp_read_only_boundary.py`'s exact technique -
proves the constraint holds for the whole module, not just the paths other tests happen to exercise.
"""

from __future__ import annotations

import ast
from pathlib import Path

_CLIENT_PATH = Path(__file__).resolve().parent.parent / "integration" / "independent_mcp_client.py"


def _imported_module_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_independent_client_imports_no_aip_internal_module():
    imports = _imported_module_names(_CLIENT_PATH.read_text())
    assert not any(name == "app" or name.startswith("app.") for name in imports), (
        "tests/integration/independent_mcp_client.py must not import any app.* module - it plays "
        "the role of a genuinely external MCP client (spec §17 scenario 22)"
    )
