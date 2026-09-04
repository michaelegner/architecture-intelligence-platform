"""v0.4.0 I2.2 - spec §17 item 17 ("the MCP adapter imports no graph repository and opens no Neo4j
session") and §8's architecture boundary ("The adapter MUST NOT open Neo4j, import graph
repositories, contain Cypher").

Static/AST-level rather than behavioral: proves the constraint holds for every code path in these
modules, not just the ones exercised by other tests. `app/mcp/wiring.py` is the one deliberate,
documented exception - it holds a `neo4j.Driver` *reference* to hand to
`ArchitectureIntelligenceService`'s constructor, but must never call `.session(`/open one itself or
import `app.graph` (see its own module docstring for why that's still within the spec §8 boundary).
"""

from __future__ import annotations

import ast
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "mcp"

_ADAPTER_MODULES = ["tools.py", "server.py", "guard.py", "app.py"]


def _imported_module_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_adapter_modules_never_import_graph_or_neo4j():
    for filename in _ADAPTER_MODULES:
        source = (_MCP_DIR / filename).read_text()
        imports = _imported_module_names(source)
        assert not any(name == "neo4j" or name.startswith("app.graph") for name in imports), (
            f"app/mcp/{filename} must not import neo4j or app.graph directly"
        )


def test_wiring_module_never_opens_a_session_or_imports_graph_repository():
    """Checks code only (not the module docstring, which discusses Cypher/sessions precisely to
    document why this module is exempt from importing `app.graph` while still touching a driver
    reference)."""
    path = _MCP_DIR / "wiring.py"
    tree = ast.parse(path.read_text())
    docstring = ast.get_docstring(tree)
    code_only = path.read_text().replace(docstring, "", 1) if docstring else path.read_text()

    imports = _imported_module_names(path.read_text())
    assert not any(name.startswith("app.graph") for name in imports)
    assert ".session(" not in code_only
    assert "MATCH (" not in code_only
