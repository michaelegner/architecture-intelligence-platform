"""v0.6.0 I3.3c: the fourth tool advertises exactly the published v0.6 contract (I3 spec §13;
decision record D1, D2, D16.2).

The advertised `inputSchema.request` must equal the published request schema, and the advertised
`outputSchema` the published answer schema, both after resolving every local `$ref`. A model change
that the published files do not carry, or that the SDK advertises differently, fails here (the
frozen-contract parity rule). The published files themselves are pinned byte for byte by
`test_locality_contracts_schema_frozen.py`.
"""

import json
from typing import Any

import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.locality_contracts import LOCALITY_TOOL_NAME
from app.architecture_intelligence.schema_export import (
    LOCALITY_ANSWER_SCHEMA_PATH,
    LOCALITY_REQUEST_SCHEMA_PATH,
)
from app.mcp.tools import register_tools


def _inline(node: Any, definitions: dict[str, Any]) -> Any:
    """Resolves every local `{"$ref": "#/$defs/X"}` in place, dropping the `$defs` table."""
    if isinstance(node, dict):
        if set(node) == {"$ref"}:
            return _inline(definitions[node["$ref"].rsplit("/", 1)[-1]], definitions)
        return {key: _inline(value, definitions) for key, value in node.items() if key != "$defs"}
    if isinstance(node, list):
        return [_inline(value, definitions) for value in node]
    return node


@pytest.fixture(scope="module")
def advertised() -> tuple[dict, dict]:
    server = MCPServer(name="test", version="0.6.0")
    register_tools(server)
    tool = server._tool_manager.get_tool(LOCALITY_TOOL_NAME)
    assert tool is not None and tool.output_schema is not None
    return tool.parameters, tool.output_schema


def _published(path) -> Any:
    schema = json.loads(path.read_text(encoding="utf-8"))
    return _inline(schema, schema.get("$defs", {}))


def test_the_advertised_request_argument_is_the_published_request_schema(advertised):
    parameters, _ = advertised
    request = _inline(parameters["properties"]["request"], parameters.get("$defs", {}))

    assert request == _published(LOCALITY_REQUEST_SCHEMA_PATH)


def test_the_advertised_output_schema_is_the_published_answer_schema(advertised):
    _, output = advertised

    assert _inline(output, output.get("$defs", {})) == _published(LOCALITY_ANSWER_SCHEMA_PATH)


def test_the_argument_wrapper_is_closed_around_exactly_one_request(advertised):
    parameters, _ = advertised

    assert parameters["additionalProperties"] is False
    assert set(parameters["properties"]) == {"request"}
    assert parameters["required"] == ["request"]
