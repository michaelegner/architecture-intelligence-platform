# MCP Tools

`v0.4.0` exposes AIP's validated architecture model to AI agents and other MCP clients as three
**read-only** tools, mounted at `/mcp` (MCP protocol `2026-07-28`, per-request envelope only — no
legacy `initialize` session handshake). See
[`docs/specifications/0.4.0/specification.md`](specifications/0.4.0/specification.md) for the full
normative contract; this page is a short practical reference.

> AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth. — [`ROADMAP.md`](../ROADMAP.md)'s v0.4 principle.

## The three tools

`tools/list` always returns exactly these three, in this fixed lexicographic order:

| Tool | Purpose |
|---|---|
| `get_architecture_drift` | Direct dependencies of a service whose current evidence qualification shows a declared-versus-observed discrepancy (`OBSERVED_ONLY` or `NOT_OBSERVED_IN_WINDOW`) — never `CONFIRMED` — bound to one stable snapshot. |
| `get_evidence` | Resolves 1-20 opaque evidence references to bounded, sanitized provenance for one explicit snapshot. |
| `get_service_dependencies` | One-hop direct dependencies of a service, qualified against declared and observed evidence and bound to a stable snapshot. |

All three:

- take one `request` argument matching their JSON Schema exactly (closed `inputSchema` —
  an unrecognized field is rejected before dispatch);
- return `structuredContent` as an `ArchitectureAnswer` envelope (`schema_version`, `producer`,
  `snapshot`, `outcome`, plus the tool-specific data/claims) validated against the tool's
  advertised `outputSchema`;
- perform zero graph writes and require no LLM API key;
- never invent, guess, or upgrade an unresolved fact — insufficient evidence is returned as a
  `limitations` entry, never silently treated as absence.

Schemas live at `schemas/architecture_intelligence/v0.4/`:
`architecture-answer.schema.json` (`get_service_dependencies`), `drift-answer.schema.json`
(`get_architecture_drift`), `evidence-answer.schema.json` (`get_evidence`).

## Calling a tool

Every request/response is JSON-RPC 2.0 over `POST /mcp`. Three headers are required and must agree
with the body (`app/mcp/guard.py` rejects a mismatch as `HEADER_MISMATCH` before dispatch):
`mcp-protocol-version`, `mcp-method`, and — for `tools/call` — `mcp-name` naming the tool. The body
must carry a `params._meta` object with `io.modelcontextprotocol/protocolVersion` and
`io.modelcontextprotocol/clientCapabilities`.

A minimal `get_service_dependencies` call:

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: tools/call' \
  -H 'mcp-name: get_service_dependencies' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_service_dependencies",
      "arguments": {
        "request": {
          "service_id": "service:order-service",
          "observation_context": {
            "environment": "demo",
            "window_start": "2026-08-26T00:00:00.000000Z",
            "window_end": "2026-08-27T00:00:00.000000Z"
          }
        }
      },
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'
```

`get_architecture_drift` takes the identical `request` shape (`service_id` +
`observation_context`); `get_evidence` instead takes `{"evidence_refs": [...], "snapshot_id":
"..."}`, both usually read from a prior answer's own `evidence_refs`/`snapshot.snapshot_id`.

## Evidence drill-down

Every claim from `get_architecture_drift`/`get_service_dependencies` carries `evidence_refs` (and,
where applicable, `resolution_evidence_refs`) — opaque IDs, never raw span/trace payload. Resolve
them with `get_evidence`, passing the **same `snapshot_id`** the first answer returned, so both
calls read the same immutable graph state.

## Try it end to end

[`examples/runtime-demo/hero-demo.md`](../examples/runtime-demo/hero-demo.md) is a complete,
deterministic, ~5-minute walkthrough: bring up AIP, seed frozen evidence, discover all three tools
via `tools/list`, then exercise the drift → evidence path via plain `curl` and see a real
`OBSERVED_ONLY` finding (`OrderService -> LegacyPricingService`) plus its evidence — no AIP internal
module, no LLM.
