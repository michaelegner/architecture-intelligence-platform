# v0.8 I1 evidence package

These are the frozen declared inputs of the v0.8 showcase ([I1 spec](../i1-declared-side-and-inventory.md) §8). Digests are in [`SHA256SUMS`](SHA256SUMS).

## Real versus authored

| Input | Origin |
|---|---|
| `c1/kafka-consumer-state.json` | **Real.** Byte copy of the v0.7.2 C1 capture ([v0.7.2 package](../../0.7.2/i2-evidence/sokol111/README.md), T `2026-10-21T17:53:57Z`); the replay test checks its digest against the v0.7.2 `SHA256SUMS` |
| `declarations/sokol111-local/` | **Authored** from each Service's `*-service-api` `pkg/events/topics.go` (I1 spec §4.2): the five Services, the pre-wave producers (`publish`) and their Topics on Redpanda. No declaration names a consumer |
| `declarations/sokol111-kafka/` | **Authored** inventory of the target broker: the four Topics without operations. The server `url` (`kafka:9092`) is a placeholder; only `x-aip-broker-id` is identity |
| `mapping/` | **Authored** from the environment configuration ([review](mapping-review.md)) |
| `upstream/` | **Real.** The two Sokol111 architecture documents at workspace commit `f6b4c1c` (`docs/architecture/`), bytes as fetched; digests pinned in I1 spec §5.4 |
| `catalog/`, `event-topic-lookup.json`, `catalog.SHA256SUMS` | **Generated** by [`harness/v08/generate_eventcatalog.py`](../../../../harness/v08/generate_eventcatalog.py) from `upstream/` (`python harness/v08/generate_eventcatalog.py docs/specifications/0.8.0/i1-evidence/upstream docs/specifications/0.8.0/i1-evidence`). Catalog digest (SHA-256 of `catalog.SHA256SUMS`, whose paths are relative to `catalog/`): `ff24602762eb2bac4d56955900b82f00f23f01dc5479a12140719753e9ae250e`. The owners are illustrative, and the entries count as confirmed promises by a disclosed demonstration assumption (parent §2) |
| [`../i1-vectors/ids.json`](../i1-vectors/ids.json) | **Computed** by [`vector-hashes.py`](../i1-vectors/vector-hashes.py), hashlib only; next to the spec, as in earlier releases |

## Pins

The Sokol111 revisions are those of the [v0.7.2 freeze](../../0.7.2/i2-evidence/sokol111/freeze.md). Each declaration's `info.description` names the repository, commit and file it was authored from.

## Replay

- `tests/integration/test_v080_i1_declarations.py` (A6): both declaration sets in one snapshot, no Service or Topic conflict.
- `tests/integration/test_v080_i1_c1_replay.py` (A7, qualification tier): C1 with the Redpanda set and mapping persists and resolves all nine attachments of the parent specification §3.5.

- `tests/unit/test_v080_i1_eventcatalog.py` (A1-A3): the generator reproduces the committed catalog byte for byte, the loaded catalog equals parent §3.1 and I1 §5.2, and every loader rejection.

[`config.yaml`](config.yaml) is the matching hosted profile. It does not register the catalog: I2 wires the EventCatalog into the import.
