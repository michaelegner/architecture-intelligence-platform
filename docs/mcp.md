# MCP Tools

AIP exposes its validated architecture model to AI agents and other MCP clients as three
**read-only** tools, mounted at the single public path `/mcp`. Two connection modes are supported,
both exposing identical Architecture Intelligence semantics — see
[`docs/adr/0014-negotiated-mcp-client-interoperability.md`](adr/0014-negotiated-mcp-client-interoperability.md)
for the decision record:

- **Direct mode** — the strict per-request envelope introduced in `v0.4.0`: every request carries
  `mcp-protocol-version: 2026-07-28`, `mcp-method`, and — for `tools/call` — `mcp-name` HTTP headers
  that must agree with a `params._meta` object in the body naming the same protocol version and
  client capabilities. No session, no `initialize` handshake. `## Calling a tool` below documents
  this path in full.
- **Negotiated mode** (`v0.4.2`) — standard MCP client negotiation, handled by the pinned MCP SDK: a
  markerless `initialize` request followed by ordinary `MCP-Protocol-Version`-headed traffic. This is
  the path a mainstream coding-agent MCP client uses out of the box; see `## Connecting a negotiated
  client` below and
  [`docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md`](specifications/0.4.2/i1-dual-mode-mcp-transport.md)
  for the exact routing contract.

`/mcp` supports `POST` only in this stateless release. Every other HTTP method — `GET`, `DELETE`,
`HEAD`, and everything else — returns `405 Method Not Allowed` with `Allow: POST` before either
mode's logic runs (and, for every method but `HEAD`, a small bounded JSON error body).

See [`docs/specifications/0.4.0/specification.md`](specifications/0.4.0/specification.md) for the
full normative tool contract (unchanged since `v0.4.0`) and
[`docs/specifications/0.4.1/specification.md`](specifications/0.4.1/specification.md) for the
qualification/messaging semantic hardening layered on top in `v0.4.1`; this page is a short
practical reference.

Every answer's `producer.version` reports the current package/producer version (`0.4.2` as of the
`v0.4.2` patch release) — this is build/producer metadata, separate from the public
`schema_version`, which stays `"0.4"` across the whole `v0.4.x` line unless the schema itself
changes.

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

## Qualification consistency with the analysis/REST surface (v0.4.1 ADR 0010)

These MCP tools require the explicit observation context defined by the v0.4 contract above —
unlike the analysis/REST path (see [`analyses.md`](analyses.md)'s runtime analyses), which may use
an implicit clock-relative default window and may allow an open-ended upper bound.

> Equivalent effective observation contexts MUST produce equivalent qualification semantics.
> Different effective observation windows MAY legitimately produce different qualifications.

Both surfaces share one semantic owner for declared-vs-observed evidence matching and coverage
classification (`app/qualification/declared_observed.py`), proven equivalent by a real Neo4j
differential test (`tests/integration/test_qualification_consistency.py`) rather than by inspection
alone.

## Calling a tool (direct mode)

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

## Connecting a negotiated client

A standard MCP client — the kind a mainstream coding-agent tool ships out of the box — connects to
`http://localhost:8000/mcp` and speaks ordinary negotiated MCP: an `initialize` request (no
`mcp-method`/`mcp-name` headers, no `params._meta`) followed by `tools/list`/`tools/call` requests
carrying only a standard `MCP-Protocol-Version` header. AIP's ingress layer routes any request
lacking AIP's direct-envelope markers to the pinned SDK's own negotiation and dispatch, which
answers it statelessly — no session identifier is issued or required. The three tools, their
schemas, and their `ArchitectureAnswer` semantics are identical to direct mode; only the transport
envelope differs. Client-specific setup steps for particular coding-agent tools are out of scope for
this page — see `examples/mcp-clients/` (added in a later `v0.4.2` increment) once available.

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
