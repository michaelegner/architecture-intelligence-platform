# AIP v0.8 I1 → I2 Handoff

Governing: [I1 spec](i1-declared-side-and-inventory.md) §11 and the [v0.8 specification](specification.md) §5 and §7 (I2).

I1 delivers declared inputs only. It makes no assessment.

## 1. What I2 receives

| Input | Where | Notes |
|---|---|---|
| Declared Services | Redpanda declaration set, `i1-evidence/declarations/sokol111-local/` | the 5 deployed Go services, `service:<deployment name>` |
| Declared producers | the same set, `PUBLISHES_TO` | Tenant → `tenant.tenant.events`; Catalog → the three `catalog.*` topics; Image → `catalog.product.events`. They decide "crosses Catalog Management?" in parent §3.5 |
| Topics | both sets; ids in [`i1-vectors/ids.json`](i1-vectors/ids.json) | broker-scoped. The Kafka set has no operations and emits no `USES_BROKER` |
| Attachments on C1 | `test_v080_i1_c1_replay.py` | the nine rows of parent §3.5, all `RESOLVED` through the Redpanda mapping |
| Catalog declarations | `load_event_catalog` (`app/sources/event_catalog_loader.py`) | typed domains (owners, member services), services (`sends`/`receives` with versions), events, teams; each with its file path; catalog digest and source revision `catalog-sha256:<digest>` |
| Event → Topic lookup | the same declaration set (`lookup`) | names a topic, not a Topic id. I2 resolves it to the inventory Topic id of each broker in capture scope (parent §3.4) |
| Registration | `SourcesConfig.event_catalogs` (`EventCatalogSourceConfig`) | exists, but is not wired into `run_all_configured_sources` |

## 2. What I2 decides and builds

- The import wiring and the promise record, kept apart from Current State (parent §5).
- How promises and Bounded Context membership are stored, with the catalog digest as provenance.
- Resolution of catalog service ids to declared Services. The ids equal the declared Service names by construction (I1 §5.2).

## 3. Rules I2 must keep

- A binding with no catalog entry is "observed, undeclared", never "observed, not promised" (parent §3.2).
- An attachment never proves that an event type was handled (parent §3.4).
- The producer side has declared evidence only.
