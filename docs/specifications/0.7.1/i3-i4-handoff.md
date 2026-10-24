# AIP v0.7.1 I3 → I4 Handoff

Governing: [I3 spec](i3-destination-consumer-public-answer.md) §7, the [I3 completion record](i3-completion-record.md), the [v0.7.1 specification](specification.md) §7 (I4 — Qualification).

I3 delivers the public answer to "for Kafka Topic D in environment E, which Services can AIP evidence-qualify as consumers?". I4 qualifies it; it does not change its semantics.

## 1. Public surface

| Surface | Query | Evidence |
|---|---|---|
| Service | `ArchitectureIntelligenceService.get_destination_consumers` | `get_destination_consumer_evidence` |
| REST | `POST /api/destination-consumers` | `POST /api/destination-consumers/evidence` |
| Negotiated MCP | `get_destination_consumers`, `request.mode: "query"` | same tool, `request.mode: "evidence"` |

- Schemas: [`destination-consumers-request.schema.json`](../../../schemas/architecture_intelligence/v0.7.1/destination-consumers-request.schema.json) and [`destination-consumers-answer.schema.json`](../../../schemas/architecture_intelligence/v0.7.1/destination-consumers-answer.schema.json), schema version `0.7.1`.
- `tools/list` now returns six tools, in lexicographic order: `get_api_consumer_usage`, `get_architecture_drift`, `get_destination_consumers`, `get_evidence`, `get_service_dependencies`, `get_service_dependencies_by_locality`. The five earlier tools are unchanged.
- Closed limitation codes: refusals `SNAPSHOT_NOT_AVAILABLE`, `UNKNOWN_DESTINATION`, `DESTINATION_NOT_KAFKA_TOPIC`, `BROKER_MISMATCH`, `NO_ACCEPTED_CAPTURE`, `CURSOR_QUERY_MISMATCH` (query only); limitations `CAPTURE_SCOPE_LIMITED` (every evaluated query), `NO_MAPPING_SOURCE`, `MORE_ROWS_AVAILABLE`, `EVIDENCE_REF_NOT_RESOLVED` (evidence only).

## 2. Deterministic fixture

- Declarations: `tests/fixtures/pubsub/kafka/declarations` (broker `kafka:cluster-a`, Topic `inventory`, Services `stock-projector`, `warehouse`).
- I1 capture and I2 mapping: written by `tests/integration/test_v071_i3_destination_consumers_service.py` (`_kafka`, `_mapping`) and imported through `run_all_configured_sources`.
- Parity: `tests/integration/test_v071_i3_destination_consumers_surface_parity.py` answers the same request through the service, REST and negotiated MCP over the real transport.

## 3. Example answers

Generated from the unit fixtures of `tests/unit/test_v071_i3_destination_consumers.py`; envelope fields `producer` and `snapshot`, and `data.request_context`, `capture_sources` and `page` are omitted here.

Resolved (a mapping source exists):

```json
{
  "schema_version": "0.7.1", "tool": "get_destination_consumers", "mode": "query", "outcome": "PARTIAL",
  "limitations": [{"code": "CAPTURE_SCOPE_LIMITED", "message": "each capture covers only its configured consumer groups at its own capture time; the rows are not a complete list of consumers"}],
  "data": {
    "mapping_source_present": true,
    "rows": [{
      "consumer_id": "consumer:0000000000000000000000000000000000000000000000000000000000000001",
      "group_id": "group-1", "outcome": "RESOLVED", "service_id": "service:stock", "limitations": [],
      "captured_at": "2026-10-18T09:00:00Z",
      "attachment_evidence_refs": ["destination-evidence:2cf7f93ec292e27c3102132f329bcbfca4223055f6ead498aca183c3f31e5f7b"],
      "mapping_evidence_refs": ["destination-evidence:e20b842263f406cceeea04923a68449b024250c9a5fce47b467d199b4fc0c834"]
    }]
  }
}
```

Unresolved (no mapping source):

```json
{
  "schema_version": "0.7.1", "tool": "get_destination_consumers", "mode": "query", "outcome": "PARTIAL",
  "limitations": [
    {"code": "CAPTURE_SCOPE_LIMITED", "message": "each capture covers only its configured consumer groups at its own capture time; the rows are not a complete list of consumers"},
    {"code": "NO_MAPPING_SOURCE", "message": "no accepted Service-mapping source exists for this broker and environment"}
  ],
  "data": {
    "mapping_source_present": false,
    "rows": [{
      "consumer_id": "consumer:0000000000000000000000000000000000000000000000000000000000000001",
      "group_id": "group-1", "outcome": "UNRESOLVED", "reason": "NO_MAPPING", "limitations": [],
      "captured_at": "2026-10-18T09:00:00Z",
      "attachment_evidence_refs": ["destination-evidence:2cf7f93ec292e27c3102132f329bcbfca4223055f6ead498aca183c3f31e5f7b"],
      "mapping_evidence_refs": []
    }]
  }
}
```

## 4. Facts I4 must respect

- Attachment at T is not message processing and not "still consumes after T"; the list is never complete; `PARTIAL` is the normal evaluated outcome.
- Only `RESOLVED` names a Service; `UNRESOLVED`, `AMBIGUOUS` and `CONFLICT` are explicit and are not "no consumer".
- The answer is a function of the snapshot: configured `telemetry.service_aliases` and the declared Topic brokers (`kafka_topic_brokers_v1`) are in the snapshot state. Graphs with Kafka consumer state have different snapshot ids from v0.7.0 for that reason.
- Declared Subscriptions are not part of this answer.

## 5. Known limitations

- A namespaced Kafka Topic always has `rows: []` (I1 attaches only to Topic ids with an empty namespace).
- An explicit-id Topic without a declared broker answers `BROKER_MISMATCH`.

## 6. Left for I4/I5

- I4: exact-candidate A/B, Kafka replay against a real system, the RabbitMQ contrast, public-surface parity on the candidate, and the product-value check (v0.7.1 specification §7).
- I5 re-freeze: `examples/release-golden-path/` (`TOOLS`, `expected.json`, README "re-freeze" section), `README.md`'s tool table and tool count, `examples/mcp-clients/cursor.md`, `examples/mcp-clients/vscode.md`, `examples/runtime-demo/hero-demo.md`; the CHANGELOG entry; release notes naming the Kafka snapshot-id change.
