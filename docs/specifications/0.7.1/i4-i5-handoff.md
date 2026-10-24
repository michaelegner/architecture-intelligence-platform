# AIP v0.7.1 I4 → I5 Handoff

Governing: the [I4 result record](i4-result-record.md), the [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) §6 and the [v0.7.1 specification](specification.md) §7 (I5 — Release). I4 ends with owner decision `CONTINUE`.

## 1. Qualified SHA

`df3a9e4f4ca7ee89aa5afdde836b2905027dd30f`: A/B IDENTICAL, all tiers and exact-candidate CI green ([execution record](i4-execution-record.md)). Up to `108390f`, `main` has not changed `app/`, `schemas/`, dependencies or the `Dockerfile`. The changes are docs, records and evidence, `ROADMAP.md`, a `README.md` badge, and two unit tests (#602, #603). I5's release-facing edits change content, so I5 decides which exact candidate it publishes and qualifies, using the v0.7.0 exact-candidate process (spec §7).

## 2. Re-freeze (carried from [I3 → I4](i3-i4-handoff.md) §6)

`tools/list` now has six tools. These are the release-facing places to re-freeze:

- `examples/release-golden-path/` (`TOOLS`, `expected.json`, the README "re-freeze" section);
- `README.md`'s tool table and tool count;
- `examples/mcp-clients/cursor.md`, `examples/mcp-clients/vscode.md`;
- `examples/runtime-demo/hero-demo.md`;
- the CHANGELOG entry.

## 3. Release notes must name

- **The Kafka snapshot-id change:** graphs with Kafka consumer state have different snapshot ids from v0.7.0, because of the `kafka_topic_brokers_v1` snapshot key (I3 decision 7).
- **Location-bound snapshot identity:** snapshot ids, evidence refs and output digests depend on the absolute checkout path ([`docs/evidence.md`](../../evidence.md) "Snapshot identity").
- **What the answer does not claim:**
  - Attachment at T is not message processing, and the list is never complete (`CAPTURE_SCOPE_LIMITED`).
  - Only `RESOLVED` names a Service.
  - RabbitMQ stays a contrast case, with no adapter.

Before the freeze, re-check every issue, CVE and limitation named in release material against its current state (spec §7 I5).

## 4. Limitations to carry

From the [result record](i4-result-record.md):
- one real local system and one agent session;
- ambiguous and conflicting mappings covered by synthetic tests only;
- `C1-incomplete` is derived;
- the capture allow-list needs upkeep;
- the location-bound identity;
- the unadvertised `evidence_refs` sort rule.

The known limitations in I3 → I4 §5 still apply: a namespaced Kafka Topic always has `rows: []`, and an explicit-id Topic without a declared broker answers `BROKER_MISMATCH`.

## 5. Not decided here

- Whether the `evidence_refs` sort rule is advertised in the schema or tool description, or the order is relaxed. This needs an owner decision.
- Whether the kit's checkout check should ignore untracked files. The kit is I4 material, and v0.7.1 does not reuse it.
