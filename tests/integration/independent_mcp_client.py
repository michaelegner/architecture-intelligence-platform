"""v0.4.0 I2.4 - the "independent MCP client" spec §17 scenarios 21-22 require: a client that
drives the full `get_service_dependencies` -> `get_evidence` golden path using only generic
HTTP/JSON-RPC, importing no AIP internal module and requiring no LLM key.

This module MUST import nothing from `app.*` - `tests/unit/test_independent_mcp_client_boundary.py`
enforces this statically (AST-level, mirroring `tests/unit/test_mcp_read_only_boundary.py`'s
technique). Only `httpx` and the standard library are used; MCP protocol/JSON-RPC framing is
hand-constructed rather than reusing a shared AIP helper - independence, not brevity, is the point.
"""

from __future__ import annotations

import httpx

MCP_PROTOCOL_VERSION = "2026-07-28"


def _meta() -> dict[str, object]:
    return {
        "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _headers(*, method: str, name: str | None = None) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": MCP_PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    return headers


def tools_list(client: httpx.Client, *, request_id: int = 1) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/list",
        "params": {"_meta": _meta()},
    }
    response = client.post("/mcp", headers=_headers(method="tools/list"), json=body)
    response.raise_for_status()
    return response.json()["result"]


def call_tool(
    client: httpx.Client, *, name: str, arguments: dict[str, object], request_id: int = 1
) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments, "_meta": _meta()},
    }
    response = client.post("/mcp", headers=_headers(method="tools/call", name=name), json=body)
    response.raise_for_status()
    return response.json()["result"]


def run_dependency_to_evidence_golden_path(
    client: httpx.Client, *, service_id: str, observation_context: dict[str, str]
) -> dict:
    """Spec §1's golden path end to end: `get_service_dependencies` -> collect every claim's
    evidence/resolution evidence refs and the answer's `snapshot_id` -> `get_evidence` on that same
    snapshot. Returns both raw tool results (`dependencies`, `evidence`) for the caller to assert
    on/validate against the advertised output schemas - this module does no assertion of its own."""
    dependencies_result = call_tool(
        client,
        name="get_service_dependencies",
        arguments={
            "request": {"service_id": service_id, "observation_context": observation_context}
        },
    )
    dependencies_answer = dependencies_result["structuredContent"]

    evidence_refs = sorted(
        {
            ref
            for claim in dependencies_answer["claims"]
            for ref in (*claim["evidence_refs"], *claim["resolution_evidence_refs"])
        }
    )
    evidence_result = call_tool(
        client,
        name="get_evidence",
        arguments={
            "request": {
                "evidence_refs": evidence_refs,
                "snapshot_id": dependencies_answer["snapshot"]["snapshot_id"],
            }
        },
    )

    return {"dependencies": dependencies_result, "evidence": evidence_result}


def run_drift_to_evidence_golden_path(
    client: httpx.Client, *, service_id: str, observation_context: dict[str, str]
) -> dict:
    """v0.4.0 I3.2 - I3 spec §44's extension of the same client rather than a second one:
    `get_architecture_drift` -> the answer's own top-level `evidence_refs` (spec §21's exact sorted
    union) and `snapshot_id` -> `get_evidence` on that same snapshot, exactly the public §22
    drill-down contract rather than a per-claim re-derivation of it. Returns both raw tool results
    (`drift`, `evidence`) for the caller to assert on/validate against the advertised output
    schemas - this module does no assertion of its own."""
    drift_result = call_tool(
        client,
        name="get_architecture_drift",
        arguments={
            "request": {"service_id": service_id, "observation_context": observation_context}
        },
    )
    drift_answer = drift_result["structuredContent"]

    evidence_refs = drift_answer["evidence_refs"]
    evidence_result = call_tool(
        client,
        name="get_evidence",
        arguments={
            "request": {
                "evidence_refs": evidence_refs,
                "snapshot_id": drift_answer["snapshot"]["snapshot_id"],
            }
        },
    )

    return {"drift": drift_result, "evidence": evidence_result}
