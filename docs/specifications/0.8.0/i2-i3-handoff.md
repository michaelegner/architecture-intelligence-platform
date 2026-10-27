# AIP v0.8 I2 → I3 Handoff

Governing: [I2 spec](i2-assessment-projection-and-tool.md) §12 and the [v0.8 specification](specification.md) §4 and §7 (I3).

## 1. What I3 receives

| Item | Where | Notes |
|---|---|---|
| The binding picture | `get_binding_picture` (service, REST and MCP with `experimental.binding-picture: true`) | query `bounded_context_id: catalog-management`, `environment: local`, `broker_ids` for both brokers |
| Expected after-wave answer | [`i2-vectors/two-broker/expected.json`](i2-vectors/two-broker/expected.json) | the §8.2 table, authored. I3's live captures must reproduce it (parent §3.6) |
| After-wave declarations | [`i2-vectors/two-broker/declarations/`](i2-vectors/two-broker/declarations/) | the I1 §4.1 rules applied to the wave |
| Kafka registration | broker `kafka:sokol111-kafka`, allow-list {Catalog, Image}, the I1 §7 Kafka mapping | the fixture's capture shape is the target |
| Profile | [`i2-evidence/config.yaml`](i2-evidence/config.yaml) | flag on; I3 adds the Kafka capture and mapping registrations and the after-wave declarations |

## 2. Rules I3 must keep

- A capture that cannot describe a group is incomplete and is rejected; never turn an acquisition failure into a detachment (parent §4.3).
- The Redpanda allow-list stays the same before and after the wave.
- Delivery through MirrorMaker 2 is checked by the broker tools and the functional test, never by AIP (parent §4.4).
